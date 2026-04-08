from flask import *
import sqlite3

import os

# Flask app
app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads/'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = "secret key"


import cv2
import numpy as np
import sqlite3
import joblib
import mediapipe as mp
from deepface.DeepFace import represent
from tensorflow.keras.applications import VGG16
from tensorflow.keras.models import Model
FEATURE_SIZE = 4096  # Change based on feature extractor output
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler

mp_face_detection = mp.solutions.face_detection
def predict_user(image):
    try:
        svm_model, scaler = joblib.load('svm_model.pkl')
    except:
        print("❌ No trained model found!")
        return None
    
    user_features = extract_features(image)
    user_features = scaler.transform([user_features])  # Apply normalization
    predicted_label = svm_model.predict(user_features)
    
    return predicted_label[0]


# 🔹 Extract user features (FIXED)
def extract_features(image):
    try:
        features_dict = represent(image, model_name="VGG-Face", enforce_detection=False)
        features = np.array(features_dict[0]["embedding"], dtype=np.float32)
    except:
        img_resized = cv2.resize(image, (224, 224))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_preprocessed = np.expand_dims(img_rgb, axis=0) / 255.0
        features = feature_extractor.predict(img_preprocessed).flatten()  # TensorFlow VGG16 fallback
    
    # 🔹 Ensure fixed size
    features = np.array(features, dtype=np.float32)
    
    if features.shape[0] > FEATURE_SIZE:
        features = features[:FEATURE_SIZE]  # Trim if too large
    elif features.shape[0] < FEATURE_SIZE:
        features = np.pad(features, (0, FEATURE_SIZE - features.shape[0]))  # Pad if too small

    return features
# 🔹 Face detection using Mediapipe
mp_face_detection = mp.solutions.face_detection

def preprocess_user(image):
    with mp_face_detection.FaceDetection(min_detection_confidence=0.5) as face_detection:
        rgb_frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = face_detection.process(rgb_frame)

        if results.detections:
            for detection in results.detections:
                bboxC = detection.location_data.relative_bounding_box
                h, w, _ = image.shape
                x, y, w, h = int(bboxC.xmin * w), int(bboxC.ymin * h), int(bboxC.width * w), int(bboxC.height * h)
                face = image[y:y+h, x:x+w]
                face_resized = cv2.resize(face, (224, 224))
                return face_resized

    return None  # No face detected
# 🔹 Predict user from video & count faces detected
def predict_from_video(video_path):
    cap = cv2.VideoCapture(video_path)
    detected_faces = 0
    predictions = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        user_face = preprocess_user(frame)
        if user_face is not None:
            detected_faces += 1
            user_label = predict_user(user_face)
            
            if user_label:
                print(user_label)
                predictions.append(user_label)

    cap.release()
    cv2.destroyAllWindows()

    if predictions:
        most_common_user = max(set(predictions), key=predictions.count)
        # video_paths = ["data/criminal/user1.mp4","data/criminal/user2.mp4","data/missing/user3.mp4"]
        data={"user_1":"criminal","user_2":"criminal","user_3":"missing"}
        # print(f"Predicted User: {most_common_user}, Detected Faces: {detected_faces} totalseconds{detected_faces/20} seconds")
        # return f"Predicted User: {most_common_user}, Detected Faces: {detected_faces} totalseconds{detected_faces/20} seconds"
        print(f"Predicted User: {most_common_user}, Detected Faces: {detected_faces} {data[most_common_user]}")
        return f"Predicted User: {most_common_user}, Detected Faces: {detected_faces} {data[most_common_user]}"
    else:
        print("No face detected in the video.")
        return None, detected_faces


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")


@app.route('/logon')
def logon():
    return render_template('signup.html')


@app.route("/signup", methods=["post", "get"])
def signup():
    username = request.form['user']
    name = request.form['name']
    email = request.form['email']
    number = request.form["mobile"]
    password = request.form['password']
    role = "student"
    con = sqlite3.connect('signup.db')
    cur = con.cursor()
    cur.execute("insert into `info` (`user`,`email`, `password`,`mobile`,`name`,'role') VALUES (?, ?, ?, ?, ?,?)",
                (username, email, password, number, name, role))
    con.commit()
    con.close()
    return render_template("index.html")


@app.route("/signin", methods=["POST"])
def signin():
    try:
        mail1 = request.form['username']  # MATCHING HTML input name
        password1 = request.form['password']
    except Exception as e:
        print("Form data error:", e)
        return "Bad form request", 400

    # ADMIN login
    if mail1 == 'admin' and password1 == 'admin':
        return redirect("/myful")

    # DB check
    con = sqlite3.connect('signup.db')
    try:
        data = con.execute(
            "SELECT `user`, `password`, role FROM info WHERE `user` = ? AND `password` = ?",
            (mail1, password1)
        ).fetchall()
        con.close()
    except Exception as e:
        print("Database error:", e)
        return "Database error", 500

    if data:
        session['username'] = data[0][0]
        return redirect("/myful")
    else:
        return render_template("signup.html", error="Invalid credentials")



@app.route("/myful")
def myful():
    return render_template("student.html")


@app.route("/predict", methods=["POST"])
def upload_and_predict():
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected!"}), 400

    # Save file
    file_path = os.path.join("uploads", file.filename)
    file.save(file_path)
    output=predict_from_video("uploads/"+file.filename)
    # Make prediction
    try:
        return render_template(
            "student.html",
            prediction=output
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def home():
    session.pop('username', None)
    return render_template("index.html")


if __name__ == '__main__':
    # Ensure folders exist
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    app.run()
