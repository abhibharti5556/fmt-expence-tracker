document.addEventListener("DOMContentLoaded", function () {
  initSidebarToggle();
  initToastAutoDismiss();
  initFileUploadPreviews();
  initPasswordToggles();
  initSubmitLock();
  initConfirmDialogs();
});

// ---------------------------------------------------------------------------
// Mobile sidebar toggle
// ---------------------------------------------------------------------------
function initSidebarToggle() {
  var sidebar = document.querySelector(".sidebar");
  var backdrop = document.querySelector(".sidebar-backdrop");
  var toggleButtons = document.querySelectorAll("[data-sidebar-toggle]");

  if (!sidebar) return;

  function open() {
    sidebar.classList.add("open");
    if (backdrop) backdrop.classList.add("show");
  }

  function close() {
    sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("show");
  }

  toggleButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (sidebar.classList.contains("open")) close();
      else open();
    });
  });

  if (backdrop) backdrop.addEventListener("click", close);
}

// ---------------------------------------------------------------------------
// Toast auto-dismiss (flash messages)
// ---------------------------------------------------------------------------
function initToastAutoDismiss() {
  document.querySelectorAll(".toast-fmt").forEach(function (toast) {
    var closeBtn = toast.querySelector(".toast-close");
    var timer = setTimeout(function () {
      dismiss(toast);
    }, 5000);

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        clearTimeout(timer);
        dismiss(toast);
      });
    }
  });

  function dismiss(toast) {
    toast.style.transition = "opacity 200ms ease";
    toast.style.opacity = "0";
    setTimeout(function () {
      toast.remove();
    }, 200);
  }
}

// ---------------------------------------------------------------------------
// File upload previews (dropzones with data-preview-target)
// ---------------------------------------------------------------------------
function initFileUploadPreviews() {
  document.querySelectorAll("input[type=file][data-preview-target]").forEach(function (input) {
    var previewId = input.getAttribute("data-preview-target");
    var preview = document.getElementById(previewId);
    if (!preview) return;

    var nameEl = preview.querySelector(".file-name");
    var sizeEl = preview.querySelector(".file-size");
    var thumbWrap = preview.querySelector(".file-thumb");

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) {
        preview.classList.remove("show");
        return;
      }

      if (nameEl) nameEl.textContent = file.name;
      if (sizeEl) sizeEl.textContent = formatFileSize(file.size);

      if (thumbWrap) {
        thumbWrap.innerHTML = "";
        if (file.type && file.type.indexOf("image/") === 0) {
          var img = document.createElement("img");
          img.alt = "Preview";
          var reader = new FileReader();
          reader.onload = function (e) {
            img.src = e.target.result;
          };
          reader.readAsDataURL(file);
          thumbWrap.appendChild(img);
        } else {
          var icon = document.createElement("div");
          icon.className = "file-icon";
          icon.innerHTML = '<i class="ph ph-file-pdf"></i>';
          thumbWrap.appendChild(icon);
        }
      }

      preview.classList.add("show");
    });
  });

  // Direct-image avatar preview (profile photo)
  document.querySelectorAll("input[type=file][data-avatar-preview]").forEach(function (input) {
    var targetId = input.getAttribute("data-avatar-preview");
    var target = document.getElementById(targetId);
    if (!target) return;

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function (e) {
        if (target.tagName === "IMG") {
          target.src = e.target.result;
        } else {
          target.style.backgroundImage = "url(" + e.target.result + ")";
        }
      };
      reader.readAsDataURL(file);
    });
  });

  document.querySelectorAll(".upload-dropzone").forEach(function (zone) {
    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) {
        e.preventDefault();
        zone.classList.add("drag-over");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function () {
        zone.classList.remove("drag-over");
      });
    });
  });
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

// ---------------------------------------------------------------------------
// Password show/hide toggles
// ---------------------------------------------------------------------------
function initPasswordToggles() {
  document.querySelectorAll("[data-password-toggle]").forEach(function (btn) {
    var targetId = btn.getAttribute("data-password-toggle");
    var input = document.getElementById(targetId);
    if (!input) return;

    btn.addEventListener("click", function () {
      var isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      btn.innerHTML = isHidden ? '<i class="ph ph-eye-slash"></i>' : '<i class="ph ph-eye"></i>';
      btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
    });
  });
}

// ---------------------------------------------------------------------------
// Submit button loading state + duplicate-submit guard
// ---------------------------------------------------------------------------
function initSubmitLock() {
  document.querySelectorAll("form[data-lock-submit]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var submitBtn = form.querySelector("[type=submit]");
      if (!submitBtn) return;

      if (form.dataset.submitted === "true") {
        e.preventDefault();
        return;
      }

      if (!form.checkValidity()) return;

      form.dataset.submitted = "true";
      submitBtn.classList.add("is-loading");
      submitBtn.disabled = true;
    });
  });
}

// ---------------------------------------------------------------------------
// Confirmation dialogs for destructive / state-changing actions
// ---------------------------------------------------------------------------
function initConfirmDialogs() {
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      var message = el.getAttribute("data-confirm");
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });
}
