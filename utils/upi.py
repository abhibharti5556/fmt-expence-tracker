from urllib.parse import quote


def build_upi_link(upi_id, payee_name, amount, note):
    """Build a standard UPI deep link. Supported UPI apps on the device can
    handle this URI scheme; the app cannot detect completion automatically,
    so the employee confirms payment manually afterward (see the payment
    confirmation step)."""
    params = (
        f"pa={quote(str(upi_id))}"
        f"&pn={quote(str(payee_name))}"
        f"&am={quote(str(amount))}"
        f"&cu=INR"
        f"&tn={quote(str(note))}"
    )
    return f"upi://pay?{params}"
