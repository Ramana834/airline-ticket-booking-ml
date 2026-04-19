from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm   # ✅ THIS LINE IS MISSING


def login_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = (request.POST.get("password") or "").strip()

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("flights:home")
        messages.error(request, "Invalid username or password")

    return render(request, "accounts/login.html")


def register_view(request):
    form = UserCreationForm()

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)

            # extra fields from POST
            user.first_name = request.POST.get("first_name", "")
            user.last_name = request.POST.get("last_name", "")
            user.email = request.POST.get("email", "")

            user.save()
            messages.success(request, "Account created successfully. Please login.")
            return redirect("users:login")

        else:
            messages.error(request, "Please correct the form.")

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("flights:home")

