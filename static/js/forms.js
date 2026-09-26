document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-toggle-password]").forEach((button) => {
    const input = document.getElementById(button.dataset.togglePassword);
    if (!input) return;
    button.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "🙈" : "👁";
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  document.querySelectorAll("[data-gender-choice]").forEach((select) => {
    const form = select.closest("form");
    const wrapper = form.querySelector("[data-gender-other]");
    const input = wrapper?.querySelector("[data-gender-other-input]");
    if (!wrapper || !input) return;
    const update = () => {
      const isOther = select.value === "Other";
      wrapper.hidden = !isOther;
      input.required = isOther;
      if (!isOther) input.value = "";
    };
    select.addEventListener("change", update);
    update();
  });

  document.querySelectorAll("form[data-password-confirm]").forEach((form) => {
    const password = form.querySelector('[name="password"]');
    const confirmation = form.querySelector("[data-confirm-password-input]");
    if (!password || !confirmation) return;
    const validate = () => confirmation.setCustomValidity(
      confirmation.value && confirmation.value !== password.value
        ? "Passwords do not match."
        : ""
    );
    password.addEventListener("input", validate);
    confirmation.addEventListener("input", validate);
    form.addEventListener("submit", validate);
  });
});
