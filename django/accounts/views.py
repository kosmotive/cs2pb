from accounts.forms import (
    JoinForm,
    LoginForm,
    SettingsForm,
)
from accounts.models import (
    Invitation,
    Squad,
    SteamProfile,
)
from csgo_app.views import add_globals_to_context

from django.contrib.auth import login as do_login
from django.contrib.auth import logout as do_logout
from django.shortcuts import (
    redirect,
    render,
)
from django.urls import reverse


def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            do_login(request, form.account)
            return redirect('squads')
    else:
        form = LoginForm()
    context = {'form': form}
    add_globals_to_context(context)
    return render(request, 'accounts/login.html', context)


def logout(request):
    do_logout(request)
    return redirect('login')


def join(request, uuid):
    invitation = Invitation.objects.get(pk=uuid)
    if request.user.pk:
        return invite(request, invitation.squad.pk, invitation.steam_profile.steamid)
    else:
        if request.method == 'POST':
            form = JoinForm(request.POST)
            form.steam_profile = invitation.steam_profile
            if form.is_valid():
                account = form.save()
                invitation.delete()
                do_login(request, account)
                return redirect('squads')
        else:
            form = JoinForm()
        form.fields['steam_profile'].initial = invitation.steam_profile.steamid
        form.fields['discord_name' ].initial = invitation.discord_name
        context = {
            'invitation': invitation,
            'form': form,
        }
        add_globals_to_context(context)
        return render(request, 'accounts/join.html', context)


def invite(request, squadid, steamid):
    steam_profile = SteamProfile.objects.get(pk=steamid)
    squad = Squad.objects.get(pk=squadid)
    invitation = steam_profile.invite(squad)
    context = {
        'invitation': invitation,
        'invite_url': invitation.absolute_url(request),
    }
    add_globals_to_context(context)
    return render(request, 'accounts/invite.html', context)


def settings(request):
    if request.method == 'POST':
        form = SettingsForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            return redirect('settings')
    else:
        form = SettingsForm(request.user)
    context = {
        'form': form,
    }
    add_globals_to_context(context)
    return render(request, 'accounts/settings.html', context)


def export_csv(request, steamid):
    from stats.models import MatchParticipation
    steam_profile = SteamProfile.objects.get(pk=steamid)
    participations = MatchParticipation.objects.filter(player = steam_profile).order_by('-pmatch__timestamp')
    return render(request, 'accounts/export.csv', dict(participations = participations), content_type = 'text/csv')


def create_notebook(request, steamid):
    steam_profile = SteamProfile.objects.get(pk=steamid)
    csv_url = request.build_absolute_uri(reverse('csv', args=(steamid,)))
    return render(request, 'accounts/create-notebook.html', dict(player = steam_profile, csv_url = csv_url))
