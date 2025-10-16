from django.http import HttpResponse
from django.conf import settings
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib import messages
from django.shortcuts import redirect
from django.db import OperationalError
import os
import time

class SessionHandlerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Try to access the session early to catch any issues
        try:
            # Force session read
            request.session.accessed = True
            request.session.modified = True
        except SessionInterrupted:
            # If session is interrupted, clear it and redirect to login
            messages.error(request, "Your session has expired. Please log in again.")
            return redirect('core:login')

        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = self.get_response(request)
                return response
            except OperationalError as e:
                if 'database is locked' in str(e):
                    # Wait a bit before retrying
                    time.sleep(0.1 * (retry_count + 1))
                    retry_count += 1
                    continue
                raise
            except SessionInterrupted:
                messages.error(request, "Your session has expired. Please log in again.")
                return redirect('core:login')
        
        # If we get here, we've exceeded our retries
        messages.error(request, "The server is currently busy. Please try again.")
        return redirect('core:home')

class FontMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Handle font requests
        if 'fonts' in request.path or 'cmaps' in request.path:
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Cache-Control'] = 'public, max-age=31536000'  # Cache for 1 year

        return response

def serve_font(request, font_name):
    font_path = os.path.join(settings.STATIC_ROOT, 'fonts', font_name)
    try:
        with open(font_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/x-font-type1')
            response['Access-Control-Allow-Origin'] = '*'
            response['Cache-Control'] = 'public, max-age=31536000'
            return response
    except FileNotFoundError:
        return HttpResponse('Font not found', status=404)