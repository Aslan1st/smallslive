function getAjaxSubmitForForm(form, formFields) {
  return function ajaxSubmit(e) {
    e.preventDefault();
    formFields.forEach(function (fieldName) {
      $("#" + fieldName + "-error").addClass('hidden');
    });
    $.ajax({
      type: "POST",
      url: form.attr('action'),
      data: form.serialize(),
      success: function (data) {
        window.location = data.location;
      },
      error: function (jqXHR, textStatus, errorThrown) {
        var response = jqXHR.responseJSON;
        formFields.forEach(function (fieldName) {
          if (response.form_errors[fieldName]) {
            $("input[name=" + fieldName + "]").parent().addClass('has-error');
            $("#" + fieldName + "-error").removeClass('hidden').text(response.form_errors[fieldName][0]);
          }
        });

        if (response.form_errors.__all__) {
          $("input[name=password1]").parent().addClass('has-error');
          $("#password1-error").removeClass('hidden').text(response.form_errors.__all__[0]);
        }
      }
    });
    return false;

  }
}

$loginForm = $('#form-login');
$loginForm.submit(getAjaxSubmitForForm($loginForm, ["login", "password"]));

$memberForm = $('#form-become-member');
$memberForm.submit(getAjaxSubmitForForm(
  $memberForm, ["first_name", "last_name", "email", "password1", "password2",
    "terms_of_service"]
));


