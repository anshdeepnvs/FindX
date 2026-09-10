// Vanilla JS for Lost & Found Portal

document.addEventListener("DOMContentLoaded", () => {
  // 1. Auto dismiss alerts after 5 seconds or allow manual close
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = "0";
      alert.style.transition = "opacity 0.5s ease";
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });

  // 2. Image upload preview
  const imageInputs = document.querySelectorAll("input[type='file'][accept*='image']");
  imageInputs.forEach(input => {
    input.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        const previewContainer = document.getElementById(input.id + "-preview");
        if (previewContainer) {
          const reader = new FileReader();
          reader.onload = (event) => {
            previewContainer.innerHTML = `<img src="${event.target.result}" style="max-height: 180px; border-radius: 8px; margin-top: 10px; border: 1px solid #cbd5e1;" />`;
          };
          reader.readAsDataURL(file);
        }
      }
    });
  });

  // 3. Confirm prompts for sensitive actions (e.g. Accept Claim, Reject Claim)
  const confirmBtns = document.querySelectorAll("[data-confirm]");
  confirmBtns.forEach(btn => {
    btn.addEventListener("click", (e) => {
      const msg = btn.getAttribute("data-confirm") || "Are you sure you want to proceed?";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
});
