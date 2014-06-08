$(document).ready(function(){
  //If customer opts in to pay for subscription during signup of trial,
  //  show credit card fields on signup page:
  function setSignupPaymentType(upgradeNowCheckbox) {

    if ($(upgradeNowCheckbox).is(":checked")) {
      $('.credit-card-fields').slideDown();
    } else {
      $('.credit-card-fields').slideUp();
    }
  }
  $('.trigger-credit-card-fields input').on('change',function(){
    setSignupPaymentType(this);
  });
  //in case webpage caches checkmark status, we need to reset the UI:
  setSignupPaymentType($('.trigger-credit-card-fields input'));
  //When user clicks on sign-up-to-mailing-list checkbox during trial sign-up
  // we want to unmute the text
  function toggleEmailSignupCheckboxLabel(checkbox) {
    if (checkbox.is(':checked')) {
      checkbox.closest('label').removeClass('text-muted');
    } else {
      checkbox.closest('label').addClass('text-muted');
    }
  }
  //Set proper visual status of mailing-list checkbox on init and change:
  toggleEmailSignupCheckboxLabel($('#div_id_subscribe input'));
  $('#signup_form').on('change','#div_id_subscribe input',function() {
    toggleEmailSignupCheckboxLabel($(this));
  });
  //Process trial sign up form
  $('#signup_form').submit(function(e){
    //AJAX 
    e.preventDefault();
    //FILL IN ERROR HANDLING
  });
  //Reset password during artist signup
  // This is very similar to Trial signup above and you may want to refactor
  $('.f-reset-password').submit(function(e){
    //AJAX 
    e.preventDefault();
    var email=$(this).find('input[name=artist_email]').val();
    //validate email address
    if (email=='') { 
      var emailContainer=$(this).find('input[name=artist_email]').closest('.form-group');
      emailContainer.addClass('has-error has-feedback').append('<span class="glyphicon glyphicon-remove form-control-feedback"></span>');
    } else {
      $('.has-error').removeClass('has-error has-feedback').find('.form-control-feedback').remove();
      $(this).html('<div class="alert alert-success"><p><strong>'+email+'</strong> has been emailed password reset instructions.</p><p><a href="#" class="send-verification-link">Resend the link</a> if you haven\'t received your email. </p><p>Remembered your password? <a href="/static_page/musician-signup-login/">Log in to continue artist registration</a></p></div>');
      //Now create a way to resend the verification link or take further action
      $('.f-reset-password').delegate('a.send-verification-link','click',function(e){
        e.preventDefault();
        //do ajax
        //Give a link to resend verification:
        $(this).closest('div.alert-success').html('(Sending...)').fadeOut(100).fadeIn(500,function() {
          $(this).replaceWith('<div class="alert alert-success">Link sent again. If you still haven\'t received the verification link, you can <a href="/static_page/musician-signup-rescue-password">try a different email address</a>,  <a href="#">email artistHelp@smallslive.com</a>, or <a href="/">return to the homepage.</a></div>');
        });
      });
    }
  }); 
  //END CUSTOMER SIGN UP FORMS

  //ARTIST SIGNUP FORMS:
  //When i approve or disapprove a master, make my name green or red
  $('.toggle-master-approve select[name=approval]').on('change',function(){
    var recording=$(this).closest('tr');
    var myName=recording.find('span.you');
    if ($(this).val()=='1') {
      myName.removeClass('not-approved');
      myName.addClass('approved');
      myName.find('span').html('&check;');
    } else {
      myName.removeClass('approved');
      myName.addClass('not-approved');
      myName.find('span').html('&cross;');
    }
  }); 
  // Let artist leave a comment about  master recording  
  $('.add-private-note .form-group').hide();
  $('.add-private-note label').on('click',function(){
    $(this).closest('div').find('.form-group').toggle();
  });   
  //END ARTIST SIGNUP FORMS
  
  
  //SUPER ADMIN forms:
  $('.artist-clearance-breakdown table').hide();
  $('.clearance-summary a').on('click',function(e){
    e.preventDefault();
    $(this).closest('td').find('table').toggle();
  });
  function checkRadio(radio) {
    if ($(radio).hasClass('extra-message')==true) {
      $('.trigger-add-extra-message').next('div').slideDown();
    } else {
      
      $('.trigger-add-extra-message').next('div').slideUp();
    }
  }
  //Let me add a welcome message when inviting artists
  $('.f-add-artist').delegate('input[name=invitation]','change',function(){
    checkRadio(this);
  });
  //Init
  if ($('.f-add-artist').length > 0) {
    checkRadio('input[name=invitation]');
  }
  //Date fields need a picker
  $('#id_date').datepicker().on('changeDate', function(ev){
    $('#id_date').datepicker('hide');
    //loading state during query - probably show spinner
    $('.f-gig .slot input').prop('disabled',true);
    $('.f-gig .slot input[type=text]').val('Checking availability..');
    
    //TODO: AJAX
    //callback function: populate the slots properly:
    //unhide the checkboxes, undisable fields, fill in labels and input slots appropriately:
    
  });;
  //Draggable musician ordering
  $('.f-gig div.sortable-list').sortable({
    //AJAX in here
    //For accessibility, we probably should use a method where we pass a value 
    //  to a hidden text input (not hidden) input field such that there is a keyboard
    //  accessible method to enter the position.
    
  });
  //Muting
  //Make checkbox+textinput fields appear selected or muted. By default, we assume
  // .text-muted was assigned to the text input
  $('.input-group-addon input').on('change',function(){
    setupInputGroupAddOns($(this));
  });
  function setupInputGroupAddOns(o) {
    var textinput=o.closest('.form-group').find('input[type=text]');
    textinput.removeClass('text-muted');
    if (o.is(':checked')==false) {
      textinput.addClass('text-muted');
    }
  }
  //init
  $('.input-group-addon input').each(function(i){
    setupInputGroupAddOns($(this));
  });
  //Make rarely used fields become unmuted on focus or blur w/ content
  $('form').delegate('#id_title, #id_subtitle','focus',function() {
    var label=$(this).closest('.form-group').find('label');
    label.removeClass('text-muted');
    $(this).on('blur',function() {
      if ($(this).val()=='') {
        label.addClass('text-muted');
      } 
    });
  });
  //Make autocompleters for name , genre, instruments
  $('.sideman_name').each(function(i){
    $(this).selectize({
      create: true,
      sortField: 'text',
      maxItems:1
    })
  });
  $('.sideman_instruments, input[name=genres], input[name=instruments]').each(function(i){
    $(this).selectize({
      delimiter: ',',
      persist: false,
      create: function(input) {
          return {
              value: input,
              text: input
          }
      }
    })
  });
  //Allow set times to be entered
  function toggle_add_set_times(checkbox,fields) {
    var fields=$(checkbox).closest('.row').next('.add_set_times');
    if ($(checkbox).is(':checked')==true) {
      fields.slideDown();
    } else {
      fields.slideUp();
    }
  }
  $('.trigger_add_set_times input').change(function() {
    toggle_add_set_times(this);
  }); 
  //init
  $('.trigger_add_set_times input').each(function(i) {
    toggle_add_set_times(this);
  }); 
  //END ADMIN FORMS
  
  //MY ACCOUNT STUFF
  //View orders -toggle order search form UIs
  $('a.trigger-search-orders-by-date').on('click',function(e) {
    e.preventDefault();
    $(this).closest('.row').hide();
    $('.row.search-orders-by-date').show();
  });
  $('a.trigger-search-orders-by-number').on('click',function(e) {
    e.preventDefault();
    $(this).closest('.row').hide();
    $('.row.search-orders-by-number').show();
  });
  //Mailing list signup from my-account page
  $('a.trigger-subscribe').on('click',function(e) {
    e.preventDefault();
    var container=$(this).closest('td');
    $(this).closest('div').fadeOut(500,function() {
      container.find('.alert').remove();
      container.prepend('<p class="alert alert-success">You are now on the SmallsLIVE mailing list.</p>');
      $('div.mailinglist-joined').fadeIn();
    });
  });
  $('a.trigger-unsubscribe').on('click',function(e) {
    e.preventDefault();
    var container=$(this).closest('td');
    $(this).closest('div').fadeOut(500,function() {
      container.find('.alert').remove();
      container.prepend('<p class="alert alert-success">You have been unsubscribed from our list.</p>');
    });
    $('div.mailinglist-not-joined').fadeIn();
  });
  //END MY ACCOUNT 
  
  
  //PUBLIC PAGES
  //EVENT PAGE/VIDEO PAGE
  //Show event description when present:
  $('.event').on('click','.trigger-show-event-description',function(e) {
    e.preventDefault();
    $(this).closest('.event-meta').find('.description').toggle();
  });
  //Favorite a video:
  $('.event').on('click','.trigger-favorite-video',function(e) {
    e.preventDefault();
    if ($(this).hasClass('btn-primary')) {
      $(this).removeClass('btn-primary').addClass('btn-success');
      $(this).html('<span class="glyphicon glyphicon-ok"></span> Favorited');
    } else {
      $(this).removeClass('btn-success').addClass('btn-primary');
      $(this).html('<span class="glyphicon glyphicon-star"></span> Favorite');
      
    }
  });
  //Request a missing video be expedited on video.html
  $('.request-video').on('click','a.trigger-request-video',function(e) {
    e.preventDefault();
    var newcount;
    var countHolder=$('.request-video .request-count');
    var requestCount=parseInt(countHolder.text());
    if ($(this).hasClass('btn-primary')) {
      $(this).removeClass('btn-primary').addClass('btn-success');
      $(this).html('<span class="glyphicon glyphicon-ok"></span> Requested');
      newCount=requestCount+1;
      countHolder.text(newCount);
    } else {
      $(this).removeClass('btn-success').addClass('btn-primary');
      $(this).html('<span class="glyphicon glyphicon-star"></span> I want it ASAP!');
      newCount=requestCount-1;
      countHolder.text(newCount);
      
    }
  });
  //Request to join artist mailing list on artist_detail.html
  $('.join-artist-mailing-list').on('submit','form',function() {
    $(this).closest('div').find('.alert').remove();
    $(this).before('<div class="alert-success alert">Request sent to artist. This is not an automated process so you may want to follow up later to make sure they received your request.</div>');
    $(this).hide();
    return false;
  });
  $('.join-artist-mailing-list .alert').on('click','a',function(e) {
    e.preventDefault();
    $('.join-artist-mailing-list .alert').remove();
    $('.join-artist-mailing-list form').slideDown();
  });
  //...or show the form even if they have and want to request again

  

});