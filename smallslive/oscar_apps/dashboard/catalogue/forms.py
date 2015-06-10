from oscar.apps.dashboard.catalogue import forms


class ProductForm(forms.ProductForm):
    class Meta(forms.ProductForm.Meta):
        fields = [
            'title', 'upc', 'short_description', 'description', 'is_discountable', 'structure']
