from django.shortcuts import render, redirect
from django.contrib.auth import (
    authenticate, 
    login, 
    logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

@csrf_protect
@require_http_methods(["GET", "POST"])
def custom_login(request):
    """
    Custom login view that works with the Cognito authentication backend.
    """
    if request.user.is_authenticated:
        return redirect('users:redirect')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if email and password:
            try:
                user = authenticate(request, username=email, password=password)
                if user is not None:
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.name}!')
                    return redirect('users:redirect')
                else:
                    messages.error(request, 'Invalid email or password.')
            except Exception as e:
                messages.error(request, f'Authentication failed: {str(e)}')
        else:
            messages.error(request, 'Please provide both email and password.')
    
    return render(request, 'users/login.html')

@login_required
def user_redirect(request):
    """
    Redirect users based on their role after login.
    - Admin users: Redirect to Django admin
    - Regular users: Redirect to landing page
    """
    user = request.user
    
    # Check if user is a superuser or staff member
    if user.is_superuser or user.is_staff:
        return redirect('admin:index')
    
    # For regular users, redirect to profile page
    return redirect('users:profile')

@login_required
def user_landing(request):
    """
    Landing page for regular users after login.
    """
    user = request.user
    context = {
        'user': user,
        'tenant': user.tenant,
        'tenant_role': user.tenant_role,
    }
    return render(request, 'users/landing.html', context)

@login_required
def custom_logout(request):
    """
    Custom logout view that redirects to login page.
    """
    logout(request)
    messages.success(request, 'You have been successfully signed out.')
    return redirect('users:login')
