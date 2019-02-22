from django.contrib import messages


def show_modal(request):
    return {'show_modal': request.GET.get('show_modal')}


def check_account_status(request):
    """Show email confirmation dialog only once after authentication"""

    user = request.user

    if not user.is_authenticated():
        return {}

    session = request.session

    flag = session.get('show_email_confirmation_dialog', True)
    show = not user.has_activated_account and flag
    session['show_email_confirmation_dialog'] = False

    return {'show_email_confirmation_dialog': show}


def check_if_event_confirmed_user(request):
    if request.user.is_anonymous():
        user_activated = False
    else:
        user_activated = request.user.has_activated_account
    try:
        return {'is_event_user_not_confirmed': not user_activated}
    except Exception as e:
        return {'is_event_user_not_confirmed': False}


def clean_messages(request):
    basket = request.basket
    count = basket.lines.filter(product__product_class__name='Gift').count()
    if not count:
        count = basket.lines.filter(product__parent__product_class__name='Gift').count()

    if count:
        storage = messages.get_messages(request)
        if storage:
            print 'Cleaning storage'
            for _ in storage:
                pass
                storage.used = True

            while len(storage._loaded_messages) > 0:
                del storage._loaded_messages[0]

    return {}