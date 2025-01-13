import os
import time
import threading
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import subprocess

# Create Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.secret_key = 'your_secret_key'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 * 1024  # 100 GB file size limit

# Ensure uploads directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def delete_file_later(file_path, delay=30):  # after 30 seconds delete files in "uploads" folder
    """
    Deletes a file after a delay.
    """
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
    
    thread = threading.Thread(target=delete)
    thread.daemon = True  # Allows the thread to terminate with the program
    thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    video = request.files['video']
    if video.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    # Save the uploaded video
    filename = secure_filename(video.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    video.save(video_path)
    
    # Schedule file deletion in 5 minutes
    delete_file_later(video_path)
    
    # Extract subtitles
    subtitle_path = os.path.splitext(video_path)[0] + ".srt"
    command = [
        "ffmpeg",
        "-i", video_path,
        "-map", "0:s:0",
        "-c:s", "srt",
        subtitle_path
    ]
    
    try:
        subprocess.run(command, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        flash(f"Error extracting subtitles: {e.stderr.decode('utf-8')}")
        return redirect(url_for('index'))
    
    # Schedule subtitle deletion in 5 minutes
    delete_file_later(subtitle_path)
    
    return send_file(subtitle_path, as_attachment=True, download_name=os.path.basename(subtitle_path))

@app.route('/combine', methods=['POST'])
def combine_video_subtitle():
    if 'video' not in request.files or 'subtitle' not in request.files:
        flash('Both video and subtitle files are required')
        return redirect(url_for('index'))
    
    video = request.files['video']
    subtitle = request.files['subtitle']
    
    if video.filename == '' or subtitle.filename == '':
        flash('Both video and subtitle files must be selected')
        return redirect(url_for('index'))
    
    # Save the uploaded files
    video_filename = secure_filename(video.filename)
    subtitle_filename = secure_filename(subtitle.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    subtitle_path = os.path.join(app.config['UPLOAD_FOLDER'], subtitle_filename)
    video.save(video_path)
    subtitle.save(subtitle_path)
    
    # Output file path
    combined_filename = os.path.splitext(video_filename)[0] + "+subtitle.mp4"
    combined_path = os.path.join(app.config['UPLOAD_FOLDER'], combined_filename)
    
    # Combine video and subtitle
    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", subtitle_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:s", "mov_text",
        combined_path
    ]
    
    try:
        subprocess.run(command, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        flash(f"Error combining video and subtitle: {e.stderr.decode('utf-8')}")
        return redirect(url_for('index'))
    
    # Schedule deletion of temporary files
    delete_file_later(video_path)
    delete_file_later(subtitle_path)
    delete_file_later(combined_path)
    
    return send_file(combined_path, as_attachment=True, download_name=combined_filename)

if __name__ == '__main__':
    app.run(debug=True)
