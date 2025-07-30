from flask import render_template, redirect, url_for, request, flash
from auth.utils import login_required
from . import admin_bp
from .decorators import role_required
from .services import (get_all_users, get_user, update_user,
                       count_active_users, recent_signups)
from .forms import UserForm, SettingsForm


# DASHBOARD
@admin_bp.route('/')
@login_required
@role_required('admin')
def dashboard():
    stats = {
        'active_users': count_active_users(),
        'signups_last_7d': recent_signups(7)
    }
    return render_template('dashboard.html', stats=stats)


# USER MANAGEMENT
@admin_bp.route('/users')
@login_required
@role_required('admin')
def list_users():
    users = get_all_users()
    return render_template('users.html', users=users)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET','POST'])
@login_required
@role_required('admin')
def edit_user(user_id):
    user = get_user(user_id)
    form = UserForm(obj=user)
    form.roles.choices = [(r.id, r.name) for r in Role.query.all()]
    if form.validate_on_submit():
        update_user(user, **form.data)
        flash('User updated', 'success')
        return redirect(url_for('.list_users'))
    return render_template('user_edit.html', form=form, user=user)


# SETTINGS
@admin_bp.route('/settings', methods=['GET','POST'])
@login_required
@role_required('admin')
def settings():
    form = SettingsForm()
    if form.validate_on_submit():
        set_setting('jwt_lifetime', form.jwt_lifetime.data)
        set_setting('email_template', form.email_template.data)
        flash('Settings saved', 'success')
        return redirect(url_for('.settings'))
    # Pre-fill form
    form.jwt_lifetime.data = get_setting('jwt_lifetime')
    form.email_template.data = get_setting('email_template')
    return render_template('settings.html', form=form)