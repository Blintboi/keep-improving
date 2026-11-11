// Native Windows select popups cannot display the bundled flag images.
export function languagePicker(control) {
  const root = control.closest(".language-switch"),
    list = root.querySelector('[role="listbox"]'),
    options = [...list.querySelectorAll('[role="option"]')];
  const close = (focus = false) => {
    list.hidden = true;
    control.setAttribute("aria-expanded", "false");
    if (focus) control.focus();
  };
  const update = (value) => {
    const selected = options.find((option) => option.dataset.language === value);
    if (!selected) return;
    control.value = value;
    root.querySelector("#language-flag").src = selected.querySelector("img").src;
    root.querySelector("#language-name").textContent = selected.textContent.trim();
    options.forEach((option) => option.setAttribute("aria-selected", String(option === selected)));
  };
  const open = () => {
    if (control.disabled) return;
    list.hidden = false;
    list.classList.toggle("opens-down", control.getBoundingClientRect().top < list.offsetHeight + 12);
    control.setAttribute("aria-expanded", "true");
    (options.find((option) => option.dataset.language === control.value) || options[0]).focus();
  };
  control.addEventListener("click", () => list.hidden ? open() : close());
  control.addEventListener("keydown", (event) => {
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      open();
    }
  });
  options.forEach((option) => option.addEventListener("click", () => {
    if (control.disabled) return close();
    const next = option.dataset.language, previous = control.value;
    close(true);
    if (next !== previous) {
      control.value = next;
      control.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }));
  list.addEventListener("keydown", (event) => {
    const index = options.indexOf(document.activeElement);
    if (["Enter", " "].includes(event.key) && index >= 0) {
      event.preventDefault();
      options[index].click();
      return;
    }
    let next;
    if (event.key === "ArrowDown") next = (index + 1) % options.length;
    if (event.key === "ArrowUp") next = (index + options.length - 1) % options.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = options.length - 1;
    if (next !== undefined) { event.preventDefault(); options[next].focus(); }
    if (event.key === "Escape") { event.preventDefault(); close(true); }
  });
  document.addEventListener("pointerdown", (event) => { if (!root.contains(event.target)) close(); });
  document.addEventListener("focusin", (event) => { if (!root.contains(event.target)) close(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) close(); });
  return { update, close };
}
