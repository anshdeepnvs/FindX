from django import forms
from .models import Item, PrivateDetail, Category


class ReportItemForm(forms.ModelForm):
    """Shared base form for both LOST and FOUND item reports."""

    class Meta:
        model = Item
        fields = [
            'title', 'category', 'brand', 'color', 'description',
            'location_name', 'city', 'state', 'country',
            'date_event', 'time_event', 'image',
        ]
        widgets = {
            'title':         forms.TextInput(attrs={'placeholder': 'e.g. Black Wildcraft Backpack'}),
            'brand':         forms.TextInput(attrs={'placeholder': 'e.g. Apple, Samsung, Wildcraft'}),
            'color':         forms.TextInput(attrs={'placeholder': 'e.g. Black, Navy Blue, Silver'}),
            'description':   forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the item clearly — visible features, condition, any notable details.'}),
            'location_name': forms.TextInput(attrs={'placeholder': 'e.g. Central Park, Gate 3 Metro Station'}),
            'city':          forms.TextInput(attrs={'placeholder': 'City'}),
            'state':         forms.TextInput(attrs={'placeholder': 'State / Province'}),
            'country':       forms.TextInput(attrs={'placeholder': 'Country'}),
            'date_event':    forms.DateInput(attrs={'type': 'date'}),
            'time_event':    forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'findx-input')
        self.fields['category'].empty_label = 'Select a category'
        self.fields['time_event'].required = False
        self.fields['image'].required = False


class PrivateDetailForm(forms.ModelForm):
    class Meta:
        model = PrivateDetail
        fields = ['hidden_info', 'challenge_question', 'serial_hint', 'additional_notes']
        widgets = {
            'hidden_info':        forms.Textarea(attrs={'rows': 3, 'placeholder': 'What unique marks, contents, or details prove ownership? e.g. stickers inside, exact serial, scratches, wallpaper description.'}),
            'challenge_question': forms.TextInput(attrs={'placeholder': 'Question to ask claimants, e.g. What is inside the front pocket?'}),
            'serial_hint':        forms.TextInput(attrs={'placeholder': 'Last 4 digits of serial / IMEI (optional)'}),
            'additional_notes':   forms.Textarea(attrs={'rows': 2, 'placeholder': 'Any additional private notes...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'findx-input')
        self.fields['challenge_question'].required = False
        self.fields['serial_hint'].required = False
        self.fields['additional_notes'].required = False


class ItemSearchForm(forms.Form):
    q        = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search items…', 'class': 'findx-input'}))
    type     = forms.ChoiceField(required=False, choices=[('', 'All Types'), ('LOST', 'Lost'), ('FOUND', 'Found')], widget=forms.Select(attrs={'class': 'findx-input'}))
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label='All Categories', widget=forms.Select(attrs={'class': 'findx-input'}))
    city     = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'City', 'class': 'findx-input'}))
