from decimal import Decimal as D
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from oscar.apps.basket.abstract_models import AbstractBasket


class Basket(AbstractBasket):
    def has_physical_products(self):
        physical_items = [item for item in self.all_lines() if item.product.is_shipping_required]
        return len(physical_items) > 0

    def has_digital_products(self):
        digital_count = self.all_lines().filter(product__product_class__requires_shipping=False).count()
        return digital_count > 0

    def digital_lines(self):
        return self.all_lines().select_related('product').filter(product__product_class__requires_shipping=False)

    def physical_lines(self):
        return self.all_lines().select_related('product').filter(Q(product__product_class__requires_shipping=True) |
                                                                 Q(product__parent__product_class__requires_shipping=True))

    def _get_digital_total(self, property):
        total = D('0.00')
        for line in self.digital_lines():
            try:
                total += getattr(line, property)
            except ObjectDoesNotExist:
                # Handle situation where the product may have been deleted
                pass
        return total

    def _get_physical_total(self, property):
        total = D('0.00')
        for line in self.physical_lines():
            try:
                total += getattr(line, property)
            except ObjectDoesNotExist:
                # Handle situation where the product may have been deleted
                pass
        return total

    @property
    def physical_total_excl_tax(self):
        """
        Return total line price excluding tax
        """
        return self._get_physical_total('line_price_excl_tax_incl_discounts')

    @property
    def digital_total_excl_tax(self):
        """
        Return total line price excluding tax
        """
        return self._get_digital_total('line_price_excl_tax_incl_discounts')

    def add_product(self, product, quantity=1, options=None, stockrecord=None):
        """
        Add a product to the basket

        'stock_info' is the price and availability data returned from
        a partner strategy class.

        The 'options' list should contains dicts with keys 'option' and 'value'
        which link the relevant product.Option model and string value
        respectively.

        Returns (line, created).
          line: the matching basket line
          created: whether the line was created or updated

        """
        if options is None:
            options = []
        if not self.id:
            self.save()

        # Ensure that all lines are the same currency
        price_currency = self.currency

        # Enable passing specific stock record
        stock_info = self.strategy.fetch_for_product(product, stockrecord)
        if price_currency and stock_info.price.currency != price_currency:
            raise ValueError((
                "Basket lines must all have the same currency. Proposed "
                "line has currency %s, while basket has currency %s")
                % (stock_info.price.currency, price_currency))

        if stock_info.stockrecord is None:
            raise ValueError((
                "Basket lines must all have stock records. Strategy hasn't "
                "found any stock record for product %s") % product)

        # Line reference is used to distinguish between variations of the same
        # product (eg T-shirts with different personalisations)
        line_ref = self._create_line_reference(
            product, stock_info.stockrecord, options)

        # Determine price to store (if one exists).  It is only stored for
        # audit and sometimes caching.
        defaults = {
            'quantity': quantity,
            'price_excl_tax': stock_info.price.excl_tax,
            'price_currency': stock_info.price.currency,
        }
        if stock_info.price.is_tax_known:
            defaults['price_incl_tax'] = stock_info.price.incl_tax
        line, created = self.lines.get_or_create(
            line_reference=line_ref,
            product=product,
            stockrecord=stock_info.stockrecord,
            defaults=defaults)
        if created:
            for option_dict in options:
                line.attributes.create(option=option_dict['option'],
                                       value=option_dict['value'])
        else:
            line.quantity += quantity
            line.save()
        self.reset_offer_applications()

        # Returning the line is useful when overriding this method.
        return line, created
    add_product.alters_data = True
    add = add_product

from oscar.apps.basket.models import *  # noqa
