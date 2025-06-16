import random
import time
import json
import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse

from .forms import SignupForm, LoginForm, GuessForm, FeedbackForm
from .firebase_config import get_firebase_services

# Get Firebase services
firebase = get_firebase_services()
db = firebase['db']
rtdb = firebase['rtdb']
auth = firebase['auth']


# Home page
def home(request):
    return render(request, 'game/home.html')


# Signup view
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = form.cleaned_data['username']

            try:
                # Create user in Firebase Authentication
                user = auth.create_user(
                    email=email,
                    password=password,
                    display_name=username
                )

                # Create user profile in Firestore
                db.collection('users').document(user.uid).set({
                    'username': username,
                    'email': email,
                    'created_at': time.time(),
                    'games_played': 0,
                    'games_won': 0,
                    'best_score': 0,
                    'is_admin': False
                })

                messages.success(request, "Account created successfully! Please log in.")
                return redirect('login')
            except Exception as e:
                messages.error(request, f"Error creating account: {str(e)}")
    else:
        form = SignupForm()

    return render(request, 'game/signup.html', {'form': form})


# Login view
def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            try:
                # Use Firebase REST API for authentication
                response = requests.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                    params={"key": request.settings.FIREBASE_CONFIG['apiKey']},
                    json={
                        "email": email,
                        "password": password,
                        "returnSecureToken": True
                    }
                )

                data = response.json()

                if response.status_code != 200:
                    messages.error(request, f"Login failed: {data.get('error', {}).get('message', 'Unknown error')}")
                    return render(request, 'game/login.html', {'form': form})

                # Store token in session
                request.session['firebase_token'] = data['idToken']

                # Get user data from Firestore
                user_doc = db.collection('users').document(data['localId']).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    request.session['user_data'] = {
                        'uid': data['localId'],
                        'email': data['email'],
                        'username': user_data.get('username', ''),
                        'is_admin': user_data.get('is_admin', False)
                    }

                messages.success(request, f"Welcome back, {user_data.get('username', '')}!")
                return redirect('game_levels')
            except Exception as e:
                messages.error(request, f"Login error: {str(e)}")
    else:
        form = LoginForm()

    return render(request, 'game/login.html', {'form': form})


# Logout view
def logout(request):
    request.session.pop('firebase_token', None)
    request.session.pop('user_data', None)
    messages.success(request, "You have been logged out successfully.")
    return redirect('home')


# Game levels selection
def game_levels(request):
    return render(request, 'game/game_levels.html')


# Game play
def play_game(request, difficulty):
    # Define ranges based on difficulty
    ranges = {
        'easy': {'min': 0, 'max': 99},
        'medium': {'min': 0, 'max': 999},
        'hard': {'min': 0, 'max': 9999}
    }

    # Get range for selected difficulty
    selected_range = ranges.get(difficulty, ranges['easy'])

    # Initialize game if not already in session
    if 'game_data' not in request.session:
        secret_number = random.randint(selected_range['min'], selected_range['max'])
        request.session['game_data'] = {
            'secret_number': secret_number,
            'attempts': 0,
            'max_attempts': 10,
            'guesses': [],
            'start_time': time.time(),
            'difficulty': difficulty,
            'game_over': False,
            'won': False
        }

    game_data = request.session['game_data']
    form = GuessForm()

    if request.method == 'POST':
        form = GuessForm(request.POST)
        if form.is_valid():
            guess = form.cleaned_data['guess']

            # Check if game is already over
            if game_data['game_over']:
                messages.warning(request, "Game is already over. Start a new game.")
                return redirect('game_levels')

            # Check if guess is within range
            if guess < selected_range['min'] or guess > selected_range['max']:
                messages.error(request, f"Guess must be between {selected_range['min']} and {selected_range['max']}.")
                return render(request, 'game/play_game.html', {'form': form, 'game_data': game_data})

            # Process guess
            game_data['attempts'] += 1

            # Determine hint
            if guess < game_data['secret_number']:
                hint = "Too Low"
            elif guess > game_data['secret_number']:
                hint = "Too High"
            else:
                hint = "Correct!"
                game_data['won'] = True
                game_data['game_over'] = True

                # Calculate score (higher is better)
                time_taken = time.time() - game_data['start_time']
                max_score = 1000
                time_penalty = min(time_taken / 2, 500)  # Cap time penalty
                attempt_penalty = (game_data['attempts'] - 1) * 50
                score = max(int(max_score - time_penalty - attempt_penalty), 10)

                game_data['score'] = score

                # Update user stats in Firestore
                user_data = request.session.get('user_data', {})
                if user_data:
                    user_ref = db.collection('users').document(user_data['uid'])
                    user_doc = user_ref.get()

                    if user_doc.exists:
                        user_stats = user_doc.to_dict()
                        games_played = user_stats.get('games_played', 0) + 1
                        games_won = user_stats.get('games_won', 0) + 1
                        best_score = max(user_stats.get('best_score', 0), score)

                        user_ref.update({
                            'games_played': games_played,
                            'games_won': games_won,
                            'best_score': best_score
                        })

                        # Add game to history
                        db.collection('game_history').add({
                            'user_id': user_data['uid'],
                            'username': user_data['username'],
                            'difficulty': difficulty,
                            'attempts': game_data['attempts'],
                            'score': score,
                            'timestamp': time.time()
                        })

                messages.success(request,
                                 f"Congratulations! You guessed the number in {game_data['attempts']} attempts. Your score: {score}")

            # Check if out of attempts
            if game_data['attempts'] >= game_data['max_attempts'] and not game_data['won']:
                game_data['game_over'] = True

                # Update user stats for games played
                user_data = request.session.get('user_data', {})
                if user_data:
                    user_ref = db.collection('users').document(user_data['uid'])
                    user_doc = user_ref.get()

                    if user_doc.exists:
                        user_stats = user_doc.to_dict()
                        games_played = user_stats.get('games_played', 0) + 1

                        user_ref.update({
                            'games_played': games_played
                        })

                messages.warning(request,
                                 f"Game over! You've used all {game_data['max_attempts']} attempts. The number was {game_data['secret_number']}.")

            # Add guess to history
            game_data['guesses'].append({
                'number': guess,
                'hint': hint
            })

            # Update session
            request.session['game_data'] = game_data

    return render(request, 'game/play_game.html', {
        'form': form,
        'game_data': game_data,
        'difficulty': difficulty,
        'range': selected_range
    })


# Reset game
def reset_game(request):
    request.session.pop('game_data', None)
    return redirect('game_levels')


# Leaderboard
def leaderboard(request):
    # Get top scores from Firestore
    leaderboard_data = []

    try:
        # Get top 20 scores
        scores_ref = db.collection('game_history').order_by('score', direction='DESCENDING').limit(20)
        scores = scores_ref.stream()

        for score in scores:
            score_data = score.to_dict()
            leaderboard_data.append({
                'username': score_data.get('username', 'Anonymous'),
                'score': score_data.get('score', 0),
                'difficulty': score_data.get('difficulty', 'easy'),
                'attempts': score_data.get('attempts', 0),
                'date': time.strftime('%Y-%m-%d', time.localtime(score_data.get('timestamp', 0)))
            })
    except Exception as e:
        messages.error(request, f"Error loading leaderboard: {str(e)}")

    return render(request, 'game/leaderboard.html', {'leaderboard': leaderboard_data})


# User profile
def profile(request):
    user_data = request.session.get('user_data', {})

    if not user_data:
        messages.warning(request, "Please log in to view your profile.")
        return redirect('login')

    # Get user stats from Firestore
    user_stats = {}
    game_history = []

    try:
        # Get user document
        user_doc = db.collection('users').document(user_data['uid']).get()

        if user_doc.exists:
            user_stats = user_doc.to_dict()

        # Get user's game history
        history_ref = db.collection('game_history').where('user_id', '==', user_data['uid']).order_by('timestamp',
                                                                                                      direction='DESCENDING').limit(
            10)
        history = history_ref.stream()

        for game in history:
            game_data = game.to_dict()
            game_history.append({
                'difficulty': game_data.get('difficulty', 'easy'),
                'score': game_data.get('score', 0),
                'attempts': game_data.get('attempts', 0),
                'date': time.strftime('%Y-%m-%d %H:%M', time.localtime(game_data.get('timestamp', 0)))
            })
    except Exception as e:
        messages.error(request, f"Error loading profile data: {str(e)}")

    return render(request, 'game/profile.html', {
        'user_data': user_data,
        'user_stats': user_stats,
        'game_history': game_history
    })


# Admin panel
def admin_panel(request):
    user_data = request.session.get('user_data', {})

    # Check if user is admin
    if not user_data.get('is_admin', False):
        messages.error(request, "You don't have permission to access the admin panel.")
        return redirect('home')

    # Get all users
    users = []
    try:
        users_ref = db.collection('users').stream()
        for user in users_ref:
            user_data = user.to_dict()
            users.append({
                'uid': user.id,
                'username': user_data.get('username', ''),
                'email': user_data.get('email', ''),
                'games_played': user_data.get('games_played', 0),
                'games_won': user_data.get('games_won', 0),
                'best_score': user_data.get('best_score', 0),
                'is_admin': user_data.get('is_admin', False)
            })
    except Exception as e:
        messages.error(request, f"Error loading users: {str(e)}")

    # Get feedback submissions
    feedback = []
    try:
        feedback_ref = db.collection('feedback').order_by('timestamp', direction='DESCENDING').stream()
        for item in feedback_ref:
            feedback_data = item.to_dict()
            feedback.append({
                'id': item.id,
                'name': feedback_data.get('name', ''),
                'email': feedback_data.get('email', ''),
                'message': feedback_data.get('message', ''),
                'rating': feedback_data.get('rating', 0),
                'date': time.strftime('%Y-%m-%d %H:%M', time.localtime(feedback_data.get('timestamp', 0)))
            })
    except Exception as e:
        messages.error(request, f"Error loading feedback: {str(e)}")

    return render(request, 'game/admin_panel.html', {
        'users': users,
        'feedback': feedback
    })


# Delete user (admin only)
@require_POST
def delete_user(request, uid):
    user_data = request.session.get('user_data', {})

    # Check if user is admin
    if not user_data.get('is_admin', False):
        return JsonResponse({'success': False, 'message': "You don't have permission to perform this action."})

    try:
        # Delete user from Firebase Auth
        auth.delete_user(uid)

        # Delete user from Firestore
        db.collection('users').document(uid).delete()

        return JsonResponse({'success': True, 'message': "User deleted successfully."})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error deleting user: {str(e)}"})


# Contact page
def contact(request):
    return render(request, 'game/contact.html')


# Feedback page
def feedback(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']
            rating = form.cleaned_data['rating']

            try:
                # Store feedback in Firestore
                db.collection('feedback').add({
                    'name': name,
                    'email': email,
                    'message': message,
                    'rating': rating,
                    'timestamp': time.time()
                })

                messages.success(request, "Thank you for your feedback!")
                return redirect('home')
            except Exception as e:
                messages.error(request, f"Error submitting feedback: {str(e)}")
    else:
        form = FeedbackForm()

    return render(request, 'game/feedback.html', {'form': form})