$(document).ready(function () {

    var checks = {
      '#card-number':  19, //4444 4444 4444 4444
      '#expiry-month':  2,
      '#expiry-year':  parseInt($('#expiry-year').attr('size')),
      '#cvc':  3,
    };
  
    $(document).on('change', 'input[name="payment_method"]', function(event) {
      var $that = $(this);
      var option  = $that.attr('id');
      if (option == 'pay-credit-card') {
        $('#credit-card-form').show();
        $('#paypal-form').hide();
      } else if (option  == 'pay-paypal') {
        $('#credit-card-form').hide();
        $('#paypal-form').show();
      }
  
    });
    function submitComplete () {

      var $supporterForm = $('#formSupporter');
      $.ajax({
        type: "POST",
        url: $supporterForm.attr('action'),
        data: $supporterForm.serialize(),
        success: function (data) {
          if(typeof completeSubpage !== "undefined"){
            notCompleteContainer.html("")
            var flowCompleteSubpage = window.subpages.get(completeSubpage);
            flowCompleteSubpage.load();
          }
          else{
            alert("ddd")

            window.location = data.location 
          }
        },
        error: function () {
        }
      });
    }
    $(document).on('submit', '#place-order', function () {

      $.ajax({
        url: $(this).attr('action'),
        type: $(this).attr('method'),
        data: $(this).serialize(),
        success: function( data ) {
          if (data && data.payment_url) {
            window.location = data.payment_url;
          } else if (data && data.success_url) {
            alert(data.success_url)

            window.location = data.success_url;
          } else if (data && data.error) {
            // go back to previous step
            backButton.click();
          } else {
            submitComplete();
          }
        },
        error: function( xhr, err ) {
          console.log(err);
        }
      });
  
      return false;
    });
  
  $(document).on('click', '.payment-method-toggle', function (event) {
    // toggle payment method buttons and forms visibility. Set input value.

    event.preventDefault();
    if ($(this).hasClass('active')) {
      return false;
    }
    $(this).addClass('active');
    $('.payment-method-toggle').not(this).removeClass('active');
    var paymentMethod = $(this).data('id');
    var selector = '#' + paymentMethod + '-form.payment-method-form';

    $(selector).removeClass('hidden');
    $('.payment-method-form').not(selector).addClass('hidden');

    // Set new value to input - payment-method
    $('#payment-method').val(paymentMethod);
    //checkConfirmButton();

    return false;
  });
    $(document).on('keyup', '#payment-form input', function (e) {
  
      if (e.which > 90 || e.which < 48) {
        return;
      }
  
      var id = '#' + $(this).attr('id');
      var keys = Object.keys(checks);
      var pos = keys.indexOf(id);
      if (pos + 1 < keys.length && $(this).val().length  == checks[id]) {
        if (id == '#expiry-year') {
          $('#name-on-card').focus();
        } else  {
          $(keys[pos + 1]).focus();
        }
      }
    });
  
    function checkInput(selector,  value) {
      $input = $(selector);
      return $input.val().length === value;
    }
  
    function checkCreditCardForm() {
      var check = true;
      $.each(checks, function(selector, value){
        if (!checkInput(selector, value)) {
          check = false;
          return;
        }
      });
  
      if (!check) {
        return false;
      }
  
      if ($('#name-on-card').val().length === 0) {
        return false;
      }
  
      return true;
  
    }
 
  
    $('.supporter-card-data .form-control').on('keyup', function() {
      $(this).removeClass('error');
  
      if ($('.supporter-card-data .form-control.error').length == 0) {
        $('#form-general-error').text('');
      }
    });
  
    function getPaymentInfoForm() {
  
      var $step = $('#supporterStepPaymentInfo');
      var url = $step.data('payment-info-url');
  
      $.ajax({
        url: url,
        type: 'get',
        success: function( data ) {
          $step.html(data);
          updatePaymentInfo();
          replaceWhiteSelects($('#supporterStepPaymentInfo')[0]);
          renderCardAnimation('#payment-form');
          showPanel(getNextStep());
        },
        error: function( xhr, err ) {
          console.log(err);
        }
      });
  
    }
  
    });
