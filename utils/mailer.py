"""Outbound email: expense-approval requests and wallet-refill requests.

Sending is best-effort: a mail failure (bad credentials, SMTP host down,
network hiccup) is logged and swallowed, never allowed to break the
employee-facing action that triggered it (submitting an expense,
requesting a refill), which must always succeed on its own merits. If
SMTP_HOST isn't configured at all, sending is skipped entirely -- this
lets the rest of these features work before real SMTP credentials are
available.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

from flask import current_app, url_for

LOGO_CID = "fmt_logo"


def send_email(to_address, subject, html_body, inline_images=None):
    """to_address: a single email string, or a list of them (e.g. every
    active admin for the wallet-refill notice) -- all get a real "To"
    header entry, not a bcc.

    inline_images: optional {content_id: file_path} to embed images the
    HTML references as <img src="cid:content_id">. Embedding the bytes in
    the email (rather than linking a URL) is what makes a logo show up
    reliably -- a URL pointing at a local/dev host wouldn't resolve for
    the recipient at all, and even a public one would need the app to
    stay reachable forever for old emails to still render."""
    to_addresses = [to_address] if isinstance(to_address, str) else list(to_address)
    to_addresses = [a for a in to_addresses if a]

    host = current_app.config.get("SMTP_HOST")
    if not host or not to_addresses:
        current_app.logger.info("SMTP not configured or no recipient; skipping email: %s", subject)
        return False

    from_address = current_app.config.get("MAIL_FROM_ADDRESS") or current_app.config.get("SMTP_USERNAME")
    from_name = current_app.config.get("MAIL_FROM_NAME", "Final Mile Techies Expense Tracker")

    if inline_images:
        msg = MIMEMultipart("related")
        msg.attach(MIMEText(html_body, "html"))
        for cid, path in inline_images.items():
            try:
                with open(path, "rb") as f:
                    image = MIMEImage(f.read())
                image.add_header("Content-ID", f"<{cid}>")
                image.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
                msg.attach(image)
            except OSError:
                current_app.logger.exception("Could not attach inline image %s", path)
    else:
        msg = MIMEText(html_body, "html")

    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_address}>"
    msg["To"] = ", ".join(to_addresses)

    try:
        port = current_app.config.get("SMTP_PORT", 587)
        username = current_app.config.get("SMTP_USERNAME")
        password = current_app.config.get("SMTP_PASSWORD")

        # Port 465 is implicit TLS (smtplib.SMTP_SSL) on virtually every
        # provider; everything else (587, 25) is plaintext-then-STARTTLS.
        # Picking the class off the port means one SMTP_PORT setting in
        # .env is enough -- no separate "which mode" flag to get wrong.
        if port == 465:
            server_cls = smtplib.SMTP_SSL
        else:
            server_cls = smtplib.SMTP

        with server_cls(host, port, timeout=10) as server:
            if port != 465 and current_app.config.get("SMTP_USE_TLS", True):
                server.starttls()
            if username:
                server.login(username, password)
            server.sendmail(from_address, to_addresses, msg.as_string())
        return True
    except Exception:
        current_app.logger.exception("Failed to send email to %s", ", ".join(to_addresses))
        return False


def _detail_row(label, value, is_last=False):
    border = "" if is_last else "border-bottom:1px solid #E4E7EC;"
    return f"""
    <tr>
      <td style="padding:10px 0;{border}font-family:Arial,Helvetica,sans-serif;font-size:13px;
      color:#8A93A2;width:130px;vertical-align:top;">{label}</td>
      <td style="padding:10px 0;{border}font-family:Arial,Helvetica,sans-serif;font-size:14px;
      color:#1E2127;vertical-align:top;">{value}</td>
    </tr>"""


def _email_shell(header_subtitle, body_html, footer_html):
    """Shared card frame for every notification email: dark header band
    with the logo on a white chip (transparent-background logo needs a
    light backing -- same treatment the app's own sidebar uses), a white
    content card, and a light footer strip.

    Written as inline-styled tables, not flexbox/grid or a <style> block
    -- the usual div/CSS approach is unreliable across real email clients
    (Outlook desktop renders HTML through Word, which ignores most of
    it), so table layout + inline styles is what actually survives."""
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F7F9;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E4E7EC;">
            <tr>
              <td style="background:#1B2130;padding:18px 28px;font-family:Arial,Helvetica,sans-serif;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="background:#FFFFFF;border-radius:6px;padding:5px 10px;">
                      <img src="cid:{LOGO_CID}" alt="Final Mile Techies" height="28" style="display:block;height:28px;width:auto;">
                    </td>
                    <td style="padding-left:12px;">
                      <span style="font-size:12px;color:#AEB4C2;">{header_subtitle}</span>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;font-family:Arial,Helvetica,sans-serif;color:#1E2127;">
                {body_html}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;background:#F9FAFB;border-top:1px solid #E4E7EC;font-family:Arial,Helvetica,sans-serif;
              font-size:11px;color:#8A93A2;line-height:1.6;">
                {footer_html}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """


def _send_with_logo(to_address, subject, html_body):
    logo_path = os.path.join(current_app.static_folder, "images", "final-mile-techies-logo.png")
    return send_email(to_address, subject, html_body, inline_images={LOGO_CID: logo_path})


def send_expense_approval_request(expense):
    """Notify the assigned admin that an expense is waiting on them, with
    one-click Approve and Reject buttons.

    Approve is a plain link straight to admin.expense_approve (GET) --
    clicking it immediately approves. If the admin isn't logged in yet,
    admin_required bounces them through admin login and `next` lands them
    right back on that same URL, already approved.

    Reject can't be one-click the same way -- a reason has to be typed
    in, so it links to the expense detail page instead, where the reject
    form (with the reason field) is right there ready to fill in."""
    admin = expense.assigned_admin
    if admin is None:
        return False

    detail_url = url_for("admin.expense_detail", expense_id=expense.id, _external=True)
    approve_url = url_for("admin.expense_approve", expense_id=expense.id, _external=True)
    amount_display = f"{expense.amount:,.2f}"
    subject = f"Approval needed: {expense.user.name} requests ₹{amount_display} for {expense.category or expense.purpose}"

    rows = "".join([
        _detail_row("Category", expense.category or expense.expense_type.title()),
        _detail_row("Purpose", expense.purpose),
        _detail_row("Submitted By", f"{expense.user.name} ({expense.user.employee_id})"),
        _detail_row("Transaction ID", f'<span style="font-family:\'Courier New\',monospace;">{expense.transaction_id}</span>', is_last=True),
    ])

    body_html = f"""
    <p style="margin:0 0 16px;font-size:15px;line-height:1.6;">Hi {admin.name},</p>
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;">
      <strong>{expense.user.name}</strong> ({expense.user.employee_id}) has submitted a
      <strong>{expense.expense_type.title()}</strong> expense and needs your approval.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FDF1DC;border-radius:8px;margin:0 0 20px;">
      <tr>
        <td style="padding:16px 20px;font-family:Arial,Helvetica,sans-serif;">
          <span style="font-size:11px;font-weight:700;color:#8A5A00;text-transform:uppercase;letter-spacing:0.04em;">Amount Requested</span><br>
          <span style="font-size:26px;font-weight:700;color:#1B2130;">&#8377;{amount_display}</span>
        </td>
      </tr>
    </table>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 26px;">
      {rows}
    </table>

    <table role="presentation" cellpadding="0" cellspacing="0">
      <tr>
        <td style="border-radius:6px;background:#1D8A5E;">
          <a href="{approve_url}" style="display:inline-block;padding:12px 24px;font-family:Arial,Helvetica,sans-serif;
          font-size:14px;font-weight:700;color:#FFFFFF;text-decoration:none;">&#10003; Approve</a>
        </td>
        <td style="width:12px;"></td>
        <td style="border-radius:6px;background:#DC2626;">
          <a href="{detail_url}" style="display:inline-block;padding:12px 24px;font-family:Arial,Helvetica,sans-serif;
          font-size:14px;font-weight:700;color:#FFFFFF;text-decoration:none;">&#10007; Reject</a>
        </td>
      </tr>
    </table>
    <p style="margin:16px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#8A93A2;line-height:1.5;">
      Approve applies immediately. Reject opens the expense so you can add a reason.
    </p>
    """
    footer_html = f"""
    If the buttons above don't work, use these links:<br>
    Approve: {approve_url}<br>
    Reject / Review: {detail_url}
    """
    html_body = _email_shell("Expense Approval Request", body_html, footer_html)
    return _send_with_logo(admin.email, subject, html_body)


def send_wallet_refill_request(user, admins, balance, recent_expenses):
    """Sent to every active (non-super-admin) admin when an employee's
    balance drops below the low-balance threshold and they hit "Request
    Wallet Refill" -- rate-limited to once per cooldown window in
    routes/employee.py, not here. Any admin can add money to any
    employee, so unlike the approval email this isn't routed to one
    specific person; it goes to the whole admin pool at once ("To"
    lists every recipient, not a bcc, so they can each see who else got
    it) and the "Add Money" button pre-selects this employee for
    whichever admin acts on it first."""
    admin_emails = [a.email for a in admins]
    if not admin_emails:
        return False

    add_money_url = url_for("admin.add_money", employee_id=user.id, _external=True)
    balance_display = f"{balance:,.2f}"
    subject = f"Wallet Refill Request: {user.name} ({user.employee_id}) — balance ₹{balance_display}"

    if recent_expenses:
        expense_rows = "".join([
            f"""
            <tr>
              <td style="padding:8px 0;border-bottom:1px solid #E4E7EC;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1E2127;">{e.created_at.strftime('%d %b %Y')}</td>
              <td style="padding:8px 0;border-bottom:1px solid #E4E7EC;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1E2127;">{e.expense_type.title()}</td>
              <td style="padding:8px 0;border-bottom:1px solid #E4E7EC;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1E2127;">{e.category or e.purpose}</td>
              <td style="padding:8px 0;border-bottom:1px solid #E4E7EC;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1E2127;text-align:right;">&#8377;{e.amount:,.2f}</td>
            </tr>"""
            for e in recent_expenses
        ])
        expenses_table = f"""
        <p style="margin:0 0 10px;font-size:13px;font-weight:700;color:#1E2127;">Recent Expenses</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
          <tr>
            <td style="padding:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8A93A2;text-transform:uppercase;">Date</td>
            <td style="padding:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8A93A2;text-transform:uppercase;">Type</td>
            <td style="padding:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8A93A2;text-transform:uppercase;">Category</td>
            <td style="padding:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8A93A2;text-transform:uppercase;text-align:right;">Amount</td>
          </tr>
          {expense_rows}
        </table>
        """
    else:
        expenses_table = """
        <p style="margin:0 0 24px;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#8A93A2;">No expenses submitted yet.</p>
        """

    body_html = f"""
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;">Hi,</p>
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;">
      <strong>{user.name}</strong> ({user.employee_id}) has requested a wallet refill — their available balance
      has dropped below &#8377;100.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FDEDED;border-radius:8px;margin:0 0 20px;">
      <tr>
        <td style="padding:16px 20px;font-family:Arial,Helvetica,sans-serif;">
          <span style="font-size:11px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:0.04em;">Current Balance</span><br>
          <span style="font-size:26px;font-weight:700;color:#1B2130;">&#8377;{balance_display}</span>
        </td>
      </tr>
    </table>

    {expenses_table}

    <table role="presentation" cellpadding="0" cellspacing="0">
      <tr>
        <td style="border-radius:6px;background:#F2A61D;">
          <a href="{add_money_url}" style="display:inline-block;padding:12px 24px;font-family:Arial,Helvetica,sans-serif;
          font-size:14px;font-weight:700;color:#1E2127;text-decoration:none;">&#8377; Add Money</a>
        </td>
      </tr>
    </table>
    <p style="margin:16px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#8A93A2;line-height:1.5;">
      The button opens Add Money with {user.name} already selected. Any admin can act on this.
    </p>
    """
    footer_html = f"""
    If the button above doesn't work, use this link:<br>
    Add Money: {add_money_url}
    """
    html_body = _email_shell("Wallet Refill Request", body_html, footer_html)
    return _send_with_logo(admin_emails, subject, html_body)
