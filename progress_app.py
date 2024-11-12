import streamlit as st
import bcrypt
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
import numpy as np
from scipy.stats import linregress
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping  # Import EarlyStopping
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os
import tensorflow as tf

# Set the random seed for reproducibility
np.random.seed(42)
tf.random.set_seed(42)

load_dotenv("cred.env")
secure_password = os.getenv("PASSWORD")
stored_hash = bcrypt.hashpw("UNKNOWN404".encode('utf-8'), bcrypt.gensalt())

# Function to handle authentication with password hashing
def authenticate():
    username = st.text_input("Username", "")
    password = st.text_input("Password", "", type="password")

    if st.button("Login"):
        if username == "adam" and bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            st.success("Login successful!")
            return True
        else:
            st.error("Invalid username or password.")
            return False

# LSTM Model and Visualization
def run_lstm_model():
    df = pd.read_csv('synthetic_bank_transactions.csv')
    df['date'] = pd.to_datetime(df['date'])
    df['day_of_week'] = df['date'].dt.dayofweek
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day

    encoder = OneHotEncoder(sparse_output=False, drop='first')
    encoded_features = encoder.fit_transform(df[['sender', 'transaction_type']])
    encoded_feature_names = encoder.get_feature_names_out(['sender', 'transaction_type'])
    df_encoded = pd.DataFrame(encoded_features, columns=encoded_feature_names, index=df.index)
    df = pd.concat([df, df_encoded], axis=1).drop(columns=['sender', 'transaction_type'])

    scaler = MinMaxScaler()
    df[['transaction_amount', 'balance']] = scaler.fit_transform(df[['transaction_amount', 'balance']])
    data = df.drop(columns=['date']).values

    def create_sequences(data, window_size):
        sequences, targets = [], []
        for i in range(len(data) - window_size):
            sequence = data[i:i + window_size]
            target = data[i + window_size, 0]
            sequences.append(sequence)
            targets.append(target)
        return np.array(sequences), np.array(targets)

    window_size = 60
    X, y = create_sequences(data, window_size)
    num_features = X.shape[2]
    X = X.reshape((X.shape[0], X.shape[1], num_features))

    model = Sequential()
    model.add(LSTM(units=50, activation='relu', input_shape=(window_size, num_features)))
    model.add(Dropout(0.2))
    model.add(Dense(1))

    model.compile(optimizer='adam', loss='mse')

    # Streamlit elements for displaying progress and loss
    st.write("Training the model...")
    epochs = 50
    batch_size = 90
    progress_bar = st.progress(0)
    loss_placeholder = st.empty()

    # Early stopping callback with more patience
    early_stopping = EarlyStopping(monitor='loss', patience=10, restore_best_weights=True)

    # Custom training loop to display loss after each epoch
    for epoch in range(epochs):
        history = model.fit(X, y, epochs=1, batch_size=batch_size, verbose=0, callbacks=[early_stopping])  # Use early stopping
        loss = history.history['loss'][0]
        progress_bar.progress((epoch + 1) / epochs)
        loss_placeholder.write(f"Epoch {epoch + 1}/{epochs}, Loss: {loss}")

        # Stop if early stopping is triggered
        if early_stopping.stopped_epoch > 0:
            st.write(f"Early stopping triggered at epoch {epoch + 1}.")
            break

    # Number of future predictions
    n_future = 90
    future_predictions = []
    current_sequence = X[-1]

    # Averaging over multiple predictions (for stability)
    for _ in range(5):  # Run multiple predictions to average them
        temp_future_predictions = []
        current_sequence = X[-1]
        for _ in range(n_future):
            next_value = model.predict(current_sequence.reshape(1, window_size, num_features))[0, 0]
            temp_future_predictions.append(next_value)
            next_sequence = np.append(current_sequence[1:], [[next_value] + [0] * (num_features - 1)], axis=0)
            current_sequence = next_sequence
        future_predictions.append(np.array(temp_future_predictions))

    # Average the predictions
    future_predictions = np.mean(future_predictions, axis=0)

    filler_array = np.zeros((future_predictions.shape[0], 2))
    filler_array[:, 0] = future_predictions
    future_predictions_rescaled = scaler.inverse_transform(filler_array)
    future_transaction_amounts = future_predictions_rescaled[:, 0]

    y_values = future_transaction_amounts.flatten()[:n_future]
    x_values = np.arange(n_future)
    slope, intercept, _, _, _ = linregress(x_values, y_values)
    trend = "Positive" if slope > 0 else "Negative"
    st.write(f"The trend of future transactions is: {trend}")

    # Visualization 1: Only Future Predictions
    plt.figure(figsize=(10, 5))
    plt.plot(y_values, label="Future Predictions", color="blue")
    plt.title("Future Transaction Amount Predictions")
    plt.xlabel("Future Transactions")
    plt.ylabel("Transaction Amount")
    plt.legend()
    st.pyplot(plt)

    # Visualization 2: Combined Past and Future Transactions
    # Rescale the original data first (only for transaction_amount and balance)
    past_transactions_rescaled = scaler.inverse_transform(df[['transaction_amount', 'balance']])[:, 0]

    # Create a combined array for past and future transactions
    combined_transactions = np.concatenate((past_transactions_rescaled[-window_size:], y_values))

    # Plot combined past and future transactions
    plt.figure(figsize=(10, 5))
    # Plot past transactions
    plt.plot(np.arange(len(past_transactions_rescaled[-window_size:])), past_transactions_rescaled[-window_size:], label="Past Transactions", color="green")
    # Plot future predictions
    plt.plot(np.arange(len(past_transactions_rescaled[-window_size:]), len(combined_transactions)), y_values, label="Future Predictions", color="blue")

    # Add a vertical line at the transition between past and future
    plt.axvline(x=window_size - 1, color="red", linestyle="--", label="Prediction Start")

    # Set the x-axis to cover the range from 0 to len(combined_transactions)
    plt.xlim(0, len(combined_transactions) - 1)

    plt.title("Combined Past and Future Transaction Amounts")
    plt.xlabel("Transactions")
    plt.ylabel("Transaction Amount")
    plt.legend()
    st.pyplot(plt)

# Main code to run the Streamlit app
def main():
    st.title("Welcome to the Streamlit App!")

    if authenticate():
        st.write("You are now logged in.")
        run_lstm_model()

if __name__ == "__main__":
    main()
