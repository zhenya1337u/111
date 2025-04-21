from flask import render_template, redirect, url_for, flash, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import logging
from datetime import datetime, timedelta

# Import the Flask app and db instance from app.py
from app import app, db

# Import and setup models
from models import UserModel
models = UserModel.setup_model(db)

# Unpack models for direct access
Guild = models['Guild']
Member = models['Member']
ModRole = models['ModRole']
AutoRole = models['AutoRole']
CustomCommand = models['CustomCommand']
Warning = models['Warning']
Mute = models['Mute']
Ban = models['Ban']
Verification = models['Verification']
RaidProtection = models['RaidProtection']
GuildStats = models['GuildStats']
ReactionRole = models['ReactionRole']
MusicSession = models['MusicSession']
CommandUsage = models['CommandUsage']
WebUser = models['WebUser']
WebSession = models['WebSession']
BackupLog = models['BackupLog']

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    """Home page route"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # For debugging
        logger.debug(f"Login attempt for email: {email}")
        
        # Find user
        user = WebUser.query.filter_by(email=email).first()
        
        # For debugging
        if user:
            logger.debug(f"Found user: {user.username}, id: {user.id}")
            # Simplified check for the demo
            if password == 'password':
                # Create session
                session['user_id'] = user.id
                session['is_admin'] = user.is_admin
                session['username'] = user.username
                
                # Update last login
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                logger.debug(f"Login successful for: {user.username}")
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                logger.debug(f"Password incorrect for: {user.username}")
        else:
            logger.debug(f"No user found with email: {email}")
        
        flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Dashboard page route"""
    if 'user_id' not in session:
        flash('Please log in to access the dashboard', 'warning')
        return redirect(url_for('login'))
    
    # Get guilds
    guilds = Guild.query.all()
    
    # Get stats
    total_guilds = len(guilds)
    total_users = 0  # This would require a more complex query in reality
    
    # Get recent commands
    recent_commands = CommandUsage.query.order_by(CommandUsage.used_at.desc()).limit(10).all()
    
    return render_template(
        'dashboard.html', 
        guilds=guilds, 
        total_guilds=total_guilds,
        total_users=total_users,
        recent_commands=recent_commands
    )

@app.route('/guilds/<int:guild_id>')
def guild_details(guild_id):
    """Guild details page route"""
    if 'user_id' not in session:
        flash('Please log in to access guild details', 'warning')
        return redirect(url_for('login'))
    
    # Get guild
    guild = Guild.query.get_or_404(guild_id)
    
    # Get guild stats
    stats = GuildStats.query.filter_by(guild_id=guild_id).order_by(GuildStats.date.desc()).first()
    
    # Get module config
    module_config = guild.module_config or {}
    
    return render_template(
        'guild_details.html',
        guild=guild,
        stats=stats,
        module_config=module_config
    )

@app.route('/api/update_module', methods=['POST'])
def update_module():
    """API endpoint to update module state"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.json
    guild_id = data.get('guild_id')
    module_name = data.get('module_name')
    state = data.get('state', False)
    
    if not guild_id or not module_name:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    
    try:
        # Get guild
        guild = Guild.query.get(guild_id)
        if not guild:
            return jsonify({'success': False, 'error': 'Guild not found'}), 404
        
        # Update module config
        if not guild.module_config:
            guild.module_config = {}
        
        guild.module_config[module_name] = state
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating module: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/stats')
def stats():
    """Stats page route"""
    if 'user_id' not in session:
        flash('Please log in to access stats', 'warning')
        return redirect(url_for('login'))
    
    # Get global stats
    guilds = Guild.query.count()
    
    # Get command usage stats
    command_stats = db.session.query(
        CommandUsage.command_name, 
        db.func.count(CommandUsage.id)
    ).group_by(CommandUsage.command_name).all()
    
    # Get active music sessions
    active_music = MusicSession.query.filter(MusicSession.ended_at == None).count()
    
    return render_template(
        'stats.html',
        guilds=guilds,
        command_stats=command_stats,
        active_music=active_music
    )

# Create all tables and add test data if needed
def initialize_database():
    with app.app_context():
        db.create_all()
        
        # Check if we need to create a test admin user
        if not WebUser.query.filter_by(email='admin@example.com').first():
            test_user = WebUser(
                id=123456789,
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('password'),
                is_admin=True
            )
            db.session.add(test_user)
            db.session.commit()
            logger.info("Created test admin user")

if __name__ == '__main__':
    # Initialize database 
    initialize_database()
    
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=True)