// Confirm dialogs: <form data-confirm="Are you sure?">
document.addEventListener("submit", function (e) {
  var msg = e.target.getAttribute("data-confirm");
  if (msg && !window.confirm(msg)) e.preventDefault();
});

// Auto-dismiss success/info alerts after 6 seconds
setTimeout(function () {
  document.querySelectorAll(".alert-success, .alert-info").forEach(function (el) {
    if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(el).close();
  });
}, 6000);

// Password confirmation check on forms that have both fields
document.querySelectorAll("form").forEach(function (form) {
  var a = form.querySelector("input[name=password], input[name=new_password]");
  var b = form.querySelector("input[name=confirm_password]");
  if (!a || !b) return;
  form.addEventListener("submit", function (e) {
    if (a.value !== b.value) { e.preventDefault(); b.setCustomValidity("Passwords do not match"); b.reportValidity(); }
  });
  b.addEventListener("input", function () { b.setCustomValidity(""); });
});

// Admin user form: show only the fields that apply to the selected role
var roleSelect = document.getElementById("role");
if (roleSelect) {
  var toggle = function () {
    document.querySelectorAll("[data-role-field]").forEach(function (el) {
      el.style.display = el.getAttribute("data-role-field") === roleSelect.value ? "" : "none";
    });
  };
  roleSelect.addEventListener("change", toggle);
  toggle();
}
