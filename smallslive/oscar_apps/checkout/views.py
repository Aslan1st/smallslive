import logging
from paypal.payflow import facade
from django import http
from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django import forms
from django.forms.models import model_to_dict
from django.shortcuts import redirect
from django.utils import six
from django.views.generic import RedirectView, View
from oscar.apps.address.models import Country
from oscar.apps.checkout import views as checkout_views
from oscar.apps.checkout import signals
from oscar.apps.checkout.views import OrderPlacementMixin
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.payment.exceptions import RedirectRequired, UnableToTakePayment, PaymentError
from oscar.apps.payment.models import SourceType, Source
from oscar.core.loading import get_class
from oscar_apps.order.models import Order
from oscar_apps.payment.exceptions import RedirectRequiredAjax
from subscriptions.mixins import PayPalMixin, StripeMixin
from subscriptions.models import Donation
from .forms import PaymentForm, BillingAddressForm


BankcardForm = get_class('payment.forms', 'BankcardForm')


OrderTotalCalculator = get_class(
    'checkout.calculators', 'OrderTotalCalculator')
Repository = get_class('shipping.repository', 'Repository')
Selector = get_class('partner.strategy', 'Selector')
selector = Selector()


logger = logging.getLogger('oscar.checkout')


class IndexView(checkout_views.IndexView):

    def form_valid(self, form):
        if form.is_guest_checkout():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            self.checkout_session.set_reservation_name(first_name, last_name)
        return super(IndexView, self).form_valid(form)

    def get_success_response(self):
        url = self.get_success_url()
        if self.request.is_ajax():
            return http.JsonResponse({'url': url})
        else:
            return redirect(url)


class ShippingMethodView(checkout_views.ShippingMethodView):

    def get_success_response(self):
        print 'Shipping method  success response'
        url = reverse('checkout:payment-method')
        if self.request.is_ajax():
            return http.JsonResponse({'url': url})
        else:
            return redirect(url)


class ShippingAddressView(checkout_views.ShippingAddressView):

    def form_valid(self, form):
        address_fields = dict(
            (k, v) for (k, v) in form.instance.__dict__.items()
            if not k.startswith('_'))
        self.checkout_session.ship_to_new_address(address_fields)
        url = self.get_success_url()
        if self.request.is_ajax():
            return http.JsonResponse({'url': url})
        else:
            return redirect(url)

    def get_template_names(self):
        if self.request.is_ajax():
            template_name = 'checkout/shipping_address_ajax.html'
        else:
            template_name = 'checkout/shipping_address.html'
        return [template_name]

    def get_context_data(self, **kwargs):
        
        context = super(ShippingAddressView, self).get_context_data(**kwargs)
        print context
        method = self.get_default_shipping_method(self.request.basket)
        shipping_charge = method.calculate(self.request.basket)
        context['shipping_charge'] = shipping_charge
        context['order_total'] = OrderTotalCalculator().calculate(
            self.request.basket, shipping_charge)
        return context

    def get_default_shipping_method(self, basket):
        return Repository().get_default_shipping_method(
            basket=self.request.basket, user=self.request.user,
            request=self.request)
    
    def get_initial(self):

        initial = self.checkout_session.new_shipping_address_fields()
        if initial:
            initial = initial.copy()
            # Convert the primary key stored in the session into a Country
            # instance
            try:
                initial['country'] = Country.objects.get(
                    iso_3166_1_a2=initial.pop('country_id'))
            except Country.DoesNotExist:
                # Hmm, the previously selected Country no longer exists. We
                # ignore this.
                pass
        if not initial:
            address = self.get_available_addresses().first()
            if address:
                initial = model_to_dict(address)

        return initial


class PaymentMethodView(checkout_views.PaymentMethodView):

    def get_success_response(self):
        url = reverse('checkout:payment-details')
        if self.request.is_ajax():
            return http.JsonResponse({'url': url})
        else:
            return redirect(url)


class PaymentDetailsView(checkout_views.PaymentDetailsView,
                         PayPalMixin, StripeMixin):
    """
    In the case of AJAX  (new become a supporter flow - gifts), we need to
    split billing from payment to match the existing payment design.
    I couldn't find a way
    """

    def get_template_names(self):

        if not self.preview:
            if self.request.is_ajax():
                template_name = 'checkout/payment_details_ajax.html'
            else:
                if self.request.basket.has_tickets():  # TODO: add venue__name='Mezzrow'
                    template_name = 'checkout/payment_details_mezzrow.html'
                else:
                    template_name = 'checkout/payment_details.html'
        else:
            if self.request.is_ajax():
                template_name = 'checkout/preview_ajax.html'
            else:
                if self.request.basket.has_tickets():
                    template_name = 'checkout/preview_mezzrow.html'
                else:
                    template_name = 'checkout/preview.html'

        return [template_name]

    def get_context_data(self, **kwargs):
        print kwargs
        basket = self.request.basket

        if basket.has_tickets():  # TODO: add parameter venue_name='Mezzrow'
            kwargs['bankcard_form'] = kwargs.get('bankcard_form', BankcardForm())
        else:
            kwargs['form'] = kwargs.get('form', PaymentForm(self.request.user))
            if 'billing_address_form' not in kwargs and self.request.user.is_authenticated():
                shipping_address = self.get_shipping_address(basket)
                billing_initial = self.get_billing_initial()
                kwargs['billing_address_form'] = BillingAddressForm(
                    shipping_address, self.request.user,
                    initial=billing_initial)

            if hasattr(self, 'token'):
                kwargs['stripe_token'] = self.token

            kwargs['card_info'] = self.checkout_session._get('payment', 'card_info')

        return super(PaymentDetailsView, self).get_context_data(**kwargs)

    def get_billing_initial(self):
        address = self.get_default_billing_address()
        if address:
            initial = model_to_dict(address)
            return initial
        else:
            return None

    def post(self, request, *args, **kwargs):
        # Posting to payment-details isn't the right thing to do.  Form
        # submissions should use the preview URL.
        if not self.preview:
            return http.HttpResponseBadRequest()
        
        self.ticket_name = {}
        self.ticket_name["first"] = self.request.POST.get('guest_first_name',"")
        self.ticket_name["last"] = self.request.POST.get('guest_last_name',"")

        # We use a custom parameter to indicate if this is an attempt to place
        # an order (normally from the preview page).  Without this, we assume a
        # payment form is being submitted from the payment details view. In
        # this case, the form needs validating and the order preview shown.
        if request.POST.get('action', '') == 'place_order':
            self.token = self.request.POST.get('card_token')
            return self.handle_place_order_submission(request, ticket_name=self.ticket_name)
        return self.handle_payment_details_submission(request, ticket_name=self.ticket_name)

    def _handle_payment_details_submission_for_mezzrow(self,
                                                       request,
                                                       billing_address_form,
                                                       payment_method, ticket_name=None): 
        """Customer can pay for Mezzrow tickets with PayPal or Credit Card.
        If CC, it is processed with PayPal PayFlow Pro"""
        self.ticket_name = ticket_name
        if payment_method == 'paypal':
            return self.render_preview(request,
                                       billing_address_form=billing_address_form,
                                       payment_method=payment_method,ticket_name=ticket_name)
        else:
            bankcard_form = BankcardForm(request.POST)
            if not bankcard_form.is_valid():
                # Form validation failed, render page again with errors
                self.preview = False
                return self.render_payment_details(request, bankcard_form=bankcard_form,
                                                   billing_address_form=billing_address_form)
            else:
                return self.render_preview(request,
                                           bankcard_form=bankcard_form,
                                           payment_method=payment_method,ticket_name=ticket_name)

    def handle_payment_details_submission(self, request, ticket_name=None):
        """"""

        basket = request.basket
        shipping_address = self.get_shipping_address(basket)
        payment_method = request.POST.get('payment_method')
        user = self.request.user
        if user.is_authenticated():
            billing_address_form = BillingAddressForm(shipping_address, user, request.POST)
            if billing_address_form.is_valid():
                print billing_address_form.errors
                if billing_address_form.cleaned_data.get('billing_option') == "same-address":
                    self.checkout_session.bill_to_shipping_address()
                else:
                    if user:
                        address = billing_address_form.save()
                        self.checkout_session.bill_to_user_address(address)
        else:
            billing_address_form = None

        if basket.has_tickets(): # TODO: add parameter venue_name='Mezzrow'
            return self._handle_payment_details_submission_for_mezzrow(
                request, billing_address_form, payment_method, ticket_name)
        else:

            form = PaymentForm(self.request.user, request.POST)

            if billing_address_form and not billing_address_form.is_valid():
                return self.render_payment_details(request, form=form,
                                                   billing_address_form=billing_address_form)

            if payment_method == 'paypal':
                return self.render_preview(request, billing_address_form=billing_address_form,
                                           payment_method='paypal')
            else:
                if payment_method == 'existing-credit-card':
                    for field in form.fields:
                        if field != 'payment_method':
                            form.fields[field].required = False
                if form.is_valid():
                    self.token = form.token
                    self.checkout_session._set('payment', 'card_info', {
                        'name': form.cleaned_data['name'],
                        'last_4': form.cleaned_data['number'][-4:],
                    })
                    return self.render_preview(request, card_token=form.token, form=form,
                                               payment_method=payment_method,
                                               billing_address_form=billing_address_form)
                else:
                    print(form.errors)
                    return self.render_payment_details(request, form=form,
                                                       billing_address_form=billing_address_form)

    def handle_place_order_submission(self, request, ticket_name=None):
        print '****************************'
        print 'handle_place_order_submission'
        print 'Basket: ', request.basket
        print request.basket.pk
        print '****************************'

        basket = request.basket
        payment_method = request.POST.get('payment_method')
        flow_type = request.POST.get('flow_type')
        submission = self.build_submission()
        submission['payment_kwargs']['payment_method'] = payment_method
        if basket.has_tickets():
            if payment_method == 'credit-card':
                bankcard_form = BankcardForm(request.POST)
                if bankcard_form.is_valid():
                    submission['payment_kwargs']['bankcard'] = bankcard_form.bankcard
                else:
                    assert False, bankcard_form.errors

        if flow_type:
            # Set flow_type in session b/c there's no easy way
            # of passing it through the order.
            request.session['flow_type'] = flow_type
        print 'Submission: '
        print submission
        return self.submit(ticket_name=ticket_name, **submission)

    def submit(self, user, basket,
               shipping_address, shipping_method,  # noqa (too complex (10))
               shipping_charge, billing_address, order_total,
               payment_kwargs=None, order_kwargs=None, ticket_name=None):

        """
        Submit a basket for order placement.

        The process runs as follows:

         * Generate an order number
         * Freeze the basket so it cannot be modified any more (important when
           redirecting the user to another site for payment as it prevents the
           basket being manipulated during the payment process).
         * Attempt to take payment for the order
           - If payment is successful, place the order
           - If a redirect is required (eg PayPal, 3DSecure), redirect
           - If payment is unsuccessful, show an appropriate error message

        :basket: The basket to submit.
        :payment_kwargs: Additional kwargs to pass to the handle_payment
                         method. It normally makes sense to pass form
                         instances (rather than model instances) so that the
                         forms can be re-rendered correctly if payment fails.
        :order_kwargs: Additional kwargs to pass to the place_order method
        """

        print '*******************************'
        print 'Submit: '
        print order_total
        print payment_kwargs
        print order_kwargs

        if payment_kwargs is None:
            payment_kwargs = {}
        if order_kwargs is None:
            order_kwargs = {}

        if not user.is_anonymous():
            first_name, last_name = user.first_name, user.last_name
            print first_name, last_name
        else:
            first_name, last_name = self.checkout_session.get_reservation_name()
            print first_name, last_name
      
        if ticket_name["first"] and ticket_name["last"]:
            order_kwargs.update({
                'first_name': ticket_name["first"],
                'last_name': ticket_name["last"]
            })

        # Taxes must be known at this point
        assert basket.is_tax_known, (
            "Basket tax must be set before a user can place an order")
        assert shipping_charge.is_tax_known, (
            "Shipping charge tax must be set before a user can place an order")

        # We generate the order number first as this will be used
        # in payment requests (ie before the order model has been
        # created).  We also save it in the session for multi-stage
        # checkouts (eg where we redirect to a 3rd party site and place
        # the order on a different request).
        order_number = self.generate_order_number(basket)
        self.checkout_session.set_order_number(order_number)
        logger.info("Order #%s: beginning submission process for basket #%d",
                    order_number, basket.id)

        # Freeze the basket so it cannot be manipulated while the customer is
        # completing payment on a 3rd party site.  Also, store a reference to
        # the basket in the session so that we know which basket to thaw if we
        # get an unsuccessful payment response when redirecting to a 3rd party
        # site.
        self.freeze_basket(basket)
        self.checkout_session.set_submitted_basket(basket)

        # We define a general error message for when an unanticipated payment
        # error occurs.
        error_msg = "{0} No payment has been taken. Please " \
                    "<a href='mailto:smallslive@gmail.com' tabindex='-1'>contact customer service</a> if this problem persists"

        signals.pre_payment.send_robust(sender=self, view=self)
        basket_lines = basket.lines.all()
        try:
            print 'try handle payment: '
            print order_number
            print order_total
            print str(shipping_charge.incl_tax)
            self.handle_payment(order_number, order_total, basket_lines, shipping_charge=str(shipping_charge.incl_tax), **payment_kwargs)
        except RedirectRequired as e:
            # Redirect required (eg PayPal, 3DS)
            logger.info("Order #%s: redirecting to %s", order_number, e.url)
            return http.HttpResponseRedirect(e.url)
        except RedirectRequiredAjax as e:
            # Redirect required (eg PayPal, 3DS)
            logger.info("Order #%s: redirecting to %s", order_number, e.url)
            print '****************************'
            print 'JsonResponse: Basket: ', self.request.basket, ' ', self.request.basket.pk
            print 'Basket: ', basket, ' ', basket.pk
            print 'Submitted basket: ', self.checkout_session.get_submitted_basket_id()
            return http.JsonResponse({'payment_url': e.url})
        except UnableToTakePayment as e:
            print 'Exception ===>'
            import sys, traceback
            ex_type, ex, tb = sys.exc_info()
            traceback.print_tb(tb)
            print str(e)
            # Something went wrong with payment but in an anticipated way.  Eg
            # their bankcard has expired, wrong card number - that kind of
            # thing. This type of exception is supposed to set a friendly error
            # message that makes sense to the customer.
            msg = six.text_type(e) + "."
            error_msg = error_msg.format(msg)
            print '******************'
            print 'UnableToTakePayment: '
            print error_msg
            logger.warning(
                "Order #%s: unable to take payment (%s) - restoring basket",
                order_number, msg)
            self.restore_frozen_basket()

            # We assume that the details submitted on the payment details view
            # were invalid (eg expired bankcard).
            if self.request.is_ajax():
                return http.JsonResponse({'error': error_msg})
            else:
                return self.render_payment_details(
                    self.request, error=error_msg, **payment_kwargs)
        except PaymentError as e:

            # A general payment error - Something went wrong which wasn't
            # anticipated.  Eg, the payment gateway is down (it happens), your
            # credentials are wrong - that king of thing.
            # It makes sense to configure the checkout logger to
            # mail admins on an error as this issue warrants some further
            # investigation.
            print str(e)
            msg = six.text_type(e) + "."
            logger.error("Order #%s: payment error (%s)", order_number, msg,
                         exc_info=True)
            self.restore_frozen_basket()
            error_msg = error_msg.format(msg)
            print '******************'
            print 'PaymentError: '
            print error_msg

            if self.request.is_ajax():
                return http.JsonResponse({'error': error_msg})
            else:
                return self.render_payment_details(
                    self.request, error=error_msg, **payment_kwargs)
        except Exception as e:
            # Unhandled exception - hopefully, you will only ever see this in
            # development...
            print 'Exception ===>'
            import sys, traceback
            ex_type, ex, tb = sys.exc_info()
            traceback.print_tb(tb)
            print str(e)

            logger.error(
                "Order #%s: unhandled exception while taking payment (%s)",
                order_number, e, exc_info=True)
            self.restore_frozen_basket()
            error_msg = error_msg.format("")
            print '******************'
            print 'Unhandled Exception: '
            print error_msg

            return self.render_preview(
                self.request, error=error_msg, **payment_kwargs)

        print 'Send post payment signal'
        signals.post_payment.send_robust(sender=self, view=self)

        # If all is ok with payment, try and place order
        logger.info("Order #%s: payment successful, placing order",
                    order_number)
        try:
            print user
            print 'Handle order placement'

            order_kwargs.update({'order_type': basket.get_order_type()})
            response = self.handle_order_placement(
                order_number, user, basket, shipping_address, shipping_method,
                shipping_charge, billing_address, order_total, **order_kwargs)
            return response
        except UnableToPlaceOrder as e:
            # It's possible that something will go wrong while trying to
            # actually place an order.  Not a good situation to be in as a
            # payment transaction may already have taken place, but needs
            # to be handled gracefully.
            msg = six.text_type(e)
            logger.error("Order #%s: unable to place order - %s",
                         order_number, msg, exc_info=True)
            self.restore_frozen_basket()
            return self.render_preview(
                self.request, error=msg, **payment_kwargs)

    def handle_successful_order(self, order):
        """
        Handle the various steps required after an order has been successfully
        placed.

        Overridden from OrderPlacementMixin.
        """
        # Send confirmation message (normally an email)
        order_type_code = 'ORDER_PLACED'
        if order.has_tickets():
            order_type_code = 'TICKET_PLACED'
        self.send_confirmation_message(order, order_type_code)

        order.set_status('Completed')
        for line in order.lines.all():
            line.set_status('Completed')

        # Flush all session data
        self.checkout_session.flush()

        # Get flow type from session
        flow_type = self.request.session.get('flow_type')

        # Save order id in session so thank-you page can load it
        self.request.session['checkout_order_id'] = order.id
        if self.request.is_ajax():
            success_url = reverse('become_supporter_complete')
            if flow_type:
                success_url += '?flow_type=' + flow_type
                # remove flow_type from session
                del self.request.session['flow_type']

                #remove messages
                storage = messages.get_messages(self.request)
                for _ in storage:
                    pass
                storage.used = True

            response = http.JsonResponse({'success_url': success_url})

        else:
            response = http.HttpResponseRedirect(self.get_success_url())
            self.send_signal(self.request, response, order)

        return response

    def get_item_list(self, basket_lines):

        items = []
        for line in basket_lines:
            item = {
                'name': line.product.get_title(),
                'price': str(line.unit_price_excl_tax),
                "sku": "N/A",
                'currency': 'USD',
                'quantity': line.quantity}
            items.append(item)

        print '***********************'
        print 'Items: '
        print items

        return items

    def handle_tickets_payment(self, order_number, total, basket_lines, **kwargs):
        """Handle payment for Mezzrow tickets
           Mezzrow is processed either with PayPal or with PayPal Payflow Pro
        """

        payment_method = kwargs.get('payment_method')
        if payment_method == 'paypal':
            item_list = self.get_item_list(basket_lines)
            currency = total.currency
            
            total = str(total.incl_tax)
            # This will redirect to PayPal and circle back to
            # the ExecutePayPalPayment class.
            self.handle_paypal_payment(currency, total, item_list,
                                       donation=False)
        else:
            bankcard = kwargs['bankcard']
            facade.sale(order_number, total.incl_tax, bankcard)

            # Record payment source and event
            source_type, is_created = SourceType.objects.get_or_create(
                name='Mezzrow Credit Card')
            source = source_type.sources.model(
                source_type=source_type,
                amount_allocated=total.incl_tax,
                amount_debited=total.incl_tax,
                currency=total.currency,
                label=bankcard.obfuscated_number)
            self.add_payment_source(source)
            self.add_payment_event('Sold', total.incl_tax)

    def handle_payment(self, order_number, total, basket_lines, shipping_charge=0.00, **kwargs):

        basket = basket_lines.first().basket
        card_token = self.request.POST.get('card_token')
        payment_method = kwargs.get('payment_method')
        self.mezzrow = False

        print '*******************'
        print 'handle_payment: '
        print 'Card token: ', card_token
        print 'Payment method: ', payment_method
        print total
        print kwargs
        print 'Basket has tickets: ', basket.has_tickets()

        if basket.has_tickets():
            self.mezzrow = True
            self.handle_tickets_payment(
                order_number,
                total, basket_lines, **kwargs)
        else:
            self.mezzrow = False
            currency = total.currency
            if card_token:
                reference = self.handle_stripe_payment(
                    card_token, order_number,
                    total, basket, basket_lines, **kwargs)
                source_name = 'Stripe Credit Card'
                source_type, __ = SourceType.objects.get_or_create(name=source_name)
                source = Source(
                    source_type=source_type,
                    currency=currency,
                    amount_allocated=total.incl_tax,
                    amount_debited=total.incl_tax,
                    reference=reference)
                self.add_payment_source(source)
                self.add_payment_event('Purchase', total.incl_tax, reference=reference)
                #Set a ongoing donation, finished when payment is confirmed
                total_deductable = basket._get_deductable_physical_total()
                donation = {
                    'user': self.request.user,
                    'currency': currency,
                    'amount': total.incl_tax,
                    'reference': reference,
                    'confirmed': False,
                    'deductable_amount': str(total_deductable)
                }
                Donation.objects.create(**donation)

            elif payment_method == 'paypal':
                item_list = self.get_item_list(basket_lines)
                total_deductable = basket._get_deductable_physical_total()
                print total_deductable
                total = str(total.incl_tax)
                # Donation will be set to True  if user is selecting gifts
                # For Tickets and  other goods, there will  be no donation.
                # 'handle_paypal_payment' returns a RedirectRequiredException
                # and the flow will be completed in ExecutePaypalPayment
                self.handle_paypal_payment(
                    currency, total, item_list,
                    donation=not basket_lines.first().basket.has_tickets(), deductable_total=total_deductable, shipping_charge=shipping_charge)

    def payment_description(self, order_number, total, **kwargs):
        return 'Order #{0} at SmallsLIVE'.format(order_number)

    def payment_metadata(self, order_number, total, basket_lines, **kwargs):
        items = {}
        for idx, item in enumerate(basket_lines, start=1):
            item_key = u'item{0}'.format(idx)
            items[item_key] = u'{0}, qty: {1}'.format(item.product.get_title(), item.quantity)
        items['order_number'] = order_number

        return items


class ExecutePayPalPaymentView(OrderPlacementMixin, PayPalMixin, View):
    """
    """

    def get(self, request, *args, **kwargs):

        """
        Receive callback from PayPal after the user has authorized the payment there.
        GET /store/checkout/paypal/execute/?paymentId=PAY-1LV98277E5422594XLP4E2MY&token=EC-1FB41424NL964725H&PayerID=EXH9W7JL6NSN8
        Confirm the payment and place the order
        """

        try:
            payment_id = self.execute_payment()
        except UnableToTakePayment as e:
            # Something went wrong with payment but in an anticipated way.  Eg
            # their bankcard has expired, wrong card number - that kind of
            # thing. This type of exception is supposed to set a friendly error
            # message that makes sense to the customer.
            error_msg = "{0} No payment has been taken. Please " \
                        "<a href='mailto:smallslive@gmail.com' tabindex='-1'>contact customer service</a> if this problem persists"
            msg = six.text_type(e) + "."
            error_msg = error_msg.format(msg)
            self.restore_frozen_basket()

            return self.render_payment_details(
                self.request, error=error_msg)

        # request.basket doesn't work b/c the basket is frozen
        basket = self.get_submitted_basket()
        strategy = selector.strategy(request=request, user=request.user)
        basket.strategy = strategy
        self.handle_order_placement(basket, payment_id)

        # Get flow type from session
        flow_type = self.request.session.get('flow_type')
        if flow_type:

            storage = messages.get_messages(self.request)
            for _ in storage:
                pass
            storage.used = True

            return http.HttpResponseRedirect(reverse(
                'become_supporter_complete') + '?payment_id={}&flow_type={}'.format(
                payment_id, flow_type))
        else:
            return http.HttpResponseRedirect(reverse(
                'checkout:thank-you') + '?payment_id={}'.format(payment_id))

    def handle_order_placement(self, basket, payment_id):

        order_number = self.checkout_session.get_order_number()
        order_kwargs = {'order_type': basket.get_order_type()}
        if basket.has_tickets():
            order_kwargs['status'] = 'Completed'
            payment_source = 'Mezzrow PayPal'
            payment_event = 'Sold'
        else:
            payment_source = 'PayPal'
            payment_event = 'Purchase'
        user = self.request.user
        if not user.is_anonymous():
            first_name, last_name = user.first_name, user.last_name
            print first_name, last_name
        else:
            user = None
            first_name, last_name = self.checkout_session.get_reservation_name()
            print first_name, last_name
            guest_email = self.checkout_session.get_guest_email()
            order_kwargs['guest_email'] = guest_email
        if first_name and last_name:
            order_kwargs.update({
                'first_name': first_name,
                'last_name': last_name
            })

        total_incl_tax = basket.total_incl_tax
        # Record payment source
        source_type, is_created = SourceType.objects.get_or_create(
            name=payment_source)
        source = Source(source_type=source_type,
                        currency='USD',
                        amount_allocated=total_incl_tax,
                        amount_debited=total_incl_tax,
                        reference=payment_id)
        self.add_payment_source(source)
        self.add_payment_event(
            payment_event, total_incl_tax, reference=payment_id)

        shipping_address = self.get_shipping_address(basket)
        shipping_method = Repository().get_default_shipping_method(
            basket=basket, user=user,
            request=self.request)
        shipping_charge = shipping_method.calculate(basket)
        order_total = self.get_order_totals(
            basket, shipping_charge=shipping_charge)
        billing_address = self.get_billing_address(shipping_address)
        # Place order
        response = super(ExecutePayPalPaymentView, self).handle_order_placement(
            order_number, user, basket,
            shipping_address, shipping_method, shipping_charge,
            billing_address, order_total, **order_kwargs)

        # Set status to completed for lines if it's a ticket.
        # 'create_lines_models' method is not passed the order status unfortunately.
        order = Order.objects.get(number=order_number)
        if order.has_tickets():
            lines = order.lines.all()
            for line in lines:
                line.set_status('Completed')

        return response


class ExecuteMezzrowPayPalPaymentView(ExecutePayPalPaymentView):
    """Class ready override PayPal payment for Mezzrow if necessary"""
    pass


