import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import requests
import pandas as pd
import datetime
import threading
import traceback

# Set the appearance and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Initialize the main window
app = ctk.CTk()
app.title("NFL Machine Learning Stats Predictor")
app.geometry("600x300")  # Adjusted height

# Variables for week and year
week_var = tk.StringVar()
year_var = tk.StringVar()

# Set default values for week and year
current_year = datetime.datetime.now().year
year_var.set(str(current_year))
week_var.set('1-8')  # Default to weeks 1-8

# Week input
week_label = ctk.CTkLabel(app, text="Weeks (e.g., 1-8 or 1,3,5-7):")
week_label.pack(pady=(20, 0))
week_entry = ctk.CTkEntry(app, textvariable=week_var)
week_entry.pack(pady=(0, 20))

# Year input
year_label = ctk.CTkLabel(app, text="Year:")
year_label.pack()
year_entry = ctk.CTkEntry(app, textvariable=year_var)
year_entry.pack(pady=(0, 20))

# Function to parse week input
def parse_weeks(week_input):
    weeks = set()
    parts = week_input.split(',')
    for part in parts:
        if '-' in part:
            start_week, end_week = part.split('-')
            start_week = int(start_week.strip())
            end_week = int(end_week.strip())
            for week in range(start_week, end_week +1):
                weeks.add(week)
        else:
            week = int(part.strip())
            weeks.add(week)
    return sorted(weeks)

# Function to display player stats (modified to include only rushing and receiving)
def display_player_stats(category, athlete_name, stats):
    # Define labels for each category
    labels = {
        "rushing": ["Attempts", "Rushing Yards", "Yards per Carry", "Rushing TDs", "Longest Run"],
        "receiving": ["Receptions", "Receiving Yards", "Yards per Reception", "Receiving TDs", "Longest Reception", "Targets"]
    }

    # Proceed only if the category is rushing or receiving
    if category in labels:
        # Zip labels with stats to create a dictionary
        return {label: stat for label, stat in zip(labels[category], stats)}
    else:
        return None  # Skip other categories

# Function to download NFL stats
def download_nfl_stats():
    try:
        weeks = parse_weeks(week_var.get())
        year = int(year_var.get())
    except ValueError:
        messagebox.showerror("Invalid Input", "Invalid week or year input.")
        return

    # Start a new thread for the long-running task
    threading.Thread(target=download_nfl_stats_thread, args=(year, weeks), daemon=True).start()

def download_nfl_stats_thread(year, weeks):
    seasontype = 2  # Regular season
    try:
        # Call the function to get NFL stats
        get_nfl_week_stats(year, weeks, seasontype)
        # Since we are in a thread, we need to use app.after() to update the GUI
        app.after(0, lambda: messagebox.showinfo("Success", f"NFL Weeks {weeks} Stats downloaded and predictions saved successfully."))
    except Exception as e:
        error_message = ''.join(traceback.format_exception(None, e, e.__traceback__))
        print(error_message)  # Print the full traceback to the console
        app.after(0, lambda: messagebox.showerror("Error", f"An error occurred while downloading NFL stats:\n{e}"))

def get_nfl_week_stats(year, weeks, seasontype=2):
    import requests
    import pandas as pd

    # Initialize list to hold all player data
    all_player_stats = []

    for week in weeks:
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={year}&seasontype={seasontype}&week={week}"
        response = requests.get(url)

        if response.status_code == 200:
            games = response.json().get('events', [])
            
            for game in games:
                game_id = game['id']
                competitors = game['competitions'][0]['competitors']
                home_team_info = [team for team in competitors if team['homeAway'] == 'home'][0]
                away_team_info = [team for team in competitors if team['homeAway'] == 'away'][0]
                home_team = home_team_info['team']['shortDisplayName']
                away_team = away_team_info['team']['shortDisplayName']
                home_score = home_team_info.get('score', 0)
                away_score = away_team_info.get('score', 0)
                
                # Retrieve detailed summary for each game
                summary_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
                summary_response = requests.get(summary_url)
                
                if summary_response.status_code == 200:
                    summary_data = summary_response.json()
                    
                    # Process each team in the game
                    for team in summary_data.get('boxscore', {}).get('players', []):
                        team_name = team['team']['displayName']
                        
                        # Iterate over each player
                        for player in team.get('statistics', []):
                            category_name = player['name']
                            
                            # Proceed only if the category is 'rushing' or 'receiving'
                            if category_name in ["rushing", "receiving"]:
                                for athlete in player.get('athletes', []):
                                    athlete_name = athlete['athlete']['displayName']
                                    stats = athlete.get('stats', [])
                                    stats_data = display_player_stats(category_name, athlete_name, stats)

                                    if stats_data:
                                        # Append player data to the list
                                        player_data = {
                                            "Week": week,
                                            "Game": f"{home_team} vs {away_team}",
                                            "Team": team_name,
                                            "Category": category_name,
                                            "Player": athlete_name,
                                            "Home Team Score": home_score,
                                            "Away Team Score": away_score,
                                        }
                                        player_data.update(stats_data)  # Add stats
                                        all_player_stats.append(player_data)
                else:
                    print(f"Failed to retrieve summary for game ID {game_id}. Status code: {summary_response.status_code}")
                    # You can choose to raise an exception here if needed
        else:
            print("Failed to retrieve data:", response.status_code)
            raise Exception(f"Failed to retrieve data for week {week}: {response.status_code}")

    if not all_player_stats:
        raise Exception("No player stats data was retrieved.")

    # Convert the list of dictionaries to a DataFrame
    df = pd.DataFrame(all_player_stats)

    # Save the actual stats to Excel
    filename = f"NFL_Weeks_{weeks[0]}-{weeks[-1]}_Player_Stats.xlsx"
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Player Stats", index=False)

        # Format Excel columns and header
        workbook = writer.book
        worksheet = writer.sheets["Player Stats"]
        worksheet.set_column("A:A", 8)   # Week column
        worksheet.set_column("B:B", 20)  # Game column
        worksheet.set_column("C:C", 15)  # Team column
        worksheet.set_column("D:D", 15)  # Category column
        worksheet.set_column("E:E", 20)  # Player column
        worksheet.set_column("F:F", 18)  # Home Team Score column
        worksheet.set_column("G:G", 18)  # Away Team Score column
        worksheet.set_column("H:Z", 15)  # Stat columns

        # Define header format with light green color
        header_format = workbook.add_format({
            "bold": True,
            "text_wrap": True,
            "valign": "top",
            "fg_color": "#D7E4BC",
            "border": 1
        })
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

    print(f"Data saved to {filename}")

    # Proceed to machine learning prediction
    train_and_predict_stats(df, max(weeks) + 1)

def train_and_predict_stats(df, next_week):
    import pandas as pd
    from sklearn.linear_model import LinearRegression
    import numpy as np

    # List of stat columns
    stat_columns = [
        'Attempts', 'Rushing Yards', 'Yards per Carry', 'Rushing TDs', 'Longest Run',
        'Receptions', 'Receiving Yards', 'Yards per Reception', 'Receiving TDs', 'Longest Reception', 'Targets'
    ]

    # Convert stat columns to numeric
    for col in stat_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Prepare a DataFrame to hold predictions
    prediction_df = df[df['Week'] == df['Week'].max()].copy()
    prediction_df['Week'] = next_week

    # Initialize an empty DataFrame for predicted stats
    predictions_list = []

    # Group the data by player
    players = df['Player'].unique()

    for player in players:
        player_data = df[df['Player'] == player].sort_values('Week')

        # Skip players without data
        if player_data.empty:
            continue

        # Prepare a dictionary to hold predictions for this player
        player_prediction = {
            'Week': next_week,
            'Game': player_data['Game'].iloc[-1],  # Assuming same game (you might need to adjust this)
            'Team': player_data['Team'].iloc[-1],
            'Category': player_data['Category'].iloc[-1],
            'Player': player_data['Player'].iloc[-1],
            'Home Team Score': player_data['Home Team Score'].iloc[-1],
            'Away Team Score': player_data['Away Team Score'].iloc[-1]
        }

        # For each stat, train a model using the player's own data
        for stat in stat_columns:
            if stat in player_data.columns:
                stat_series = player_data[['Week', stat]].dropna()

                if len(stat_series) >= 2:
                    # Use Week as the independent variable and stat as dependent variable
                    X = stat_series['Week'].values.reshape(-1, 1)
                    y = stat_series[stat].values

                    # Train linear regression model
                    model = LinearRegression()
                    model.fit(X, y)

                    # Predict for the next week
                    y_pred = model.predict(np.array([[next_week]]))

                    # Add predicted stat to player_prediction dict
                    player_prediction[f'Predicted {stat}'] = y_pred[0]
                elif len(stat_series) == 1:
                    # Only one data point, use it as the prediction
                    player_prediction[f'Predicted {stat}'] = stat_series[stat].values[0]
                else:
                    # No data for this stat
                    player_prediction[f'Predicted {stat}'] = np.nan
            else:
                player_prediction[f'Predicted {stat}'] = np.nan

        predictions_list.append(player_prediction)

    # Convert the list of predictions to a DataFrame
    prediction_df = pd.DataFrame(predictions_list)

    # Reorder columns to match the original stats spreadsheet
    columns_order = ['Week', 'Game', 'Team', 'Category', 'Player', 'Home Team Score', 'Away Team Score']
    for stat in stat_columns:
        pred_col = f'Predicted {stat}'
        if pred_col in prediction_df.columns:
            columns_order.append(pred_col)

    prediction_df = prediction_df[columns_order]

    # Save the predictions to Excel
    pred_filename = f"NFL_Predicted_Stats_Week_{next_week}.xlsx"
    with pd.ExcelWriter(pred_filename, engine="xlsxwriter") as writer:
        prediction_df.to_excel(writer, sheet_name="Predicted Stats", index=False)
        workbook = writer.book
        worksheet = writer.sheets["Predicted Stats"]

        # Set column widths and formatting
        for i, col in enumerate(prediction_df.columns):
            column_len = max(prediction_df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, column_len)

        # Define header format with light green color
        header_format = workbook.add_format({
            "bold": True,
            "text_wrap": True,
            "valign": "top",
            "fg_color": "#D7E4BC",
            "border": 1
        })
        for col_num, value in enumerate(prediction_df.columns.values):
            worksheet.write(0, col_num, value, header_format)

    print(f"Predicted stats saved to {pred_filename}")

# Download NFL Stats Excel Button and Note
stats_button = ctk.CTkButton(app, text="Download Offensive NFL Stats + Prediction Excel", command=download_nfl_stats)
stats_button.pack(pady=(20, 5))
stats_note = ctk.CTkLabel(app, text="Consists of selected weeks' offensive player's stats. Predictions for next week will be generated.")
stats_note.pack(pady=(0, 10))

# Start the main event loop
app.mainloop()
