from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from django.core.exceptions import ValidationError

from .models import Account, SteamProfile

from api import api, SteamAPIUser


class SteamProfileCreationForm(UserCreationForm):

    class Meta:
        model = SteamProfile
        fields = ('steamid',)


class AccountCreationForm(UserCreationForm):

    class Meta:
        model = Account
        fields = ('steam_profile', 'steam_auth', 'email_address', 'discord_name', 'last_sharecode')


class AccountChangeForm(UserChangeForm):

    class Meta:
        model = Account
        fields = ('steam_auth', 'email_address', 'discord_name', 'last_sharecode')


def test_steam_auth(steam_profile, steam_auth):
    return api.test_steam_auth(steam_profile.find_oldest_sharecode(), SteamAPIUser(steam_profile.steamid, steam_auth))


class FormDiscordMixin:


    def clean_discord_name(form):
        discord_name = form.cleaned_data['discord_name']
        parts = discord_name.split('#')
        if len(discord_name) > 0 and (len(parts) != 2 or not parts[1].isnumeric() or len(parts[1]) != 4 or len(parts[0]) == 0):
            raise ValidationError('Not a valid Discord name.')
        return discord_name


class FormSteamAuthMixin:

    def __init__(self):
        if not hasattr(self, 'ok'): self.ok = dict()

    def clean_steam_auth(self):
        steam_auth = self.cleaned_data['steam_auth']
        if not test_steam_auth(self.steam_profile, steam_auth):
            self.ok['steam_auth'] = False
            raise ValidationError('Code is invalid or Steam servers are not responding.')
        self.ok['steam_auth'] = True
        return steam_auth


class JoinForm(UserCreationForm, FormDiscordMixin, FormSteamAuthMixin):

    def __init__(self, *args, **kwargs):
        super(UserCreationForm  , self).__init__(*args, **kwargs)
        super(FormDiscordMixin  , self).__init__()
        super(FormSteamAuthMixin, self).__init__()

    class Meta:
        model = Account
        fields = ('steam_profile', 'steam_auth', 'email_address', 'discord_name')
        widgets = {'steam_profile': forms.HiddenInput()}


class LoginForm(forms.Form):

    steamid = forms.CharField(label='Steam ID', required=False)
    email_address = forms.EmailField(label='Email address', required=False)
    password = forms.CharField(label='Password', widget=forms.PasswordInput())

    def clean(self):
        data = super().clean()
        steamid  = data.get('steamid', '')
        email    = data.get('email_address', '')
        password = data.get('password', '')
        if (steamid == '') == (email == ''):
            raise ValidationError('Please enter either your Email address or your Steam ID.')
        accounts = Account.objects.filter(steam_profile__steamid = steamid) | Account.objects.filter(email_address = email)
        if len(accounts) == 0 or not accounts.get().check_password(password):
            raise ValidationError('Credentials not found.')
        else:
            self.account = accounts.get()


class SettingsForm(UserChangeForm, FormDiscordMixin, FormSteamAuthMixin):

    password = None

    class Meta:
        model = Account
        fields = ('clean_name', 'steam_auth', 'email_address', 'discord_name')

    def __init__(self, instance, data=None, *args, **kwargs):
        if data is None: data = dict(
            steam_auth    = instance.steam_auth,
            email_address = instance.email_address,
            discord_name  = instance.discord_name,
            clean_name    = instance.clean_name)
        super(UserChangeForm    , self).__init__(data, *args, **kwargs)
        super(FormDiscordMixin  , self).__init__()
        super(FormSteamAuthMixin, self).__init__()
        self.instance = instance

    @property
    def steam_profile(self):
        return self.instance.steam_profile

