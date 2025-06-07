import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import matplotlib.colors as mcolors
import itertools
import io
import time

from cp_sat import cp_sat_generate_schedule

def generate_schedule(num_doctors, days_in_month, starting_day, disallowed_pairs):
    weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    starting_day_name = weekdays[starting_day]
    
    solution = cp_sat_generate_schedule(num_doctors, days_in_month, starting_day_name, disallowed_pairs)
    
    schedule = [-1 for _ in range(days_in_month)]
    if solution:
        schedule = solution

    # Transform to DataFrame
    weeks = [[]]
    for _ in range(starting_day):
        weeks[-1].append(None)
        
    for day, person in enumerate(schedule, start=1):
        if len(weeks[-1]) == 7:
            weeks.append([])
        weeks[-1].append(person)
        
    while len(weeks[-1]) < 7:
        weeks[-1].append(None)
    
    # Add headers for weekdays
    df = pd.DataFrame(
        weeks, columns=["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    )
    return df

def add_day_numbers(df, start_day, total_days, doctors_names):
    day_number = 1
    updated_df = df.copy()

    # Ensure all columns are of dtype object to handle strings
    updated_df = updated_df.astype(object)

    for row_idx, row in updated_df.iterrows():
        for col_idx, col_name in enumerate(updated_df.columns):
            if row_idx == 0 and col_idx < start_day:  # Skip initial empty slots
                updated_df.at[row_idx, col_name] = ""
            elif day_number > total_days:  # Stop when exceeding total days
                updated_df.at[row_idx, col_name] = ""
            else:
                # Replace with "Doctor Name (Day Number)"
                current_value = updated_df.at[row_idx, col_name]
                if not pd.isna(current_value):  # Only update non-NaN values
                    doctor_name = doctors_names.get(current_value, "")
                    updated_df.at[row_idx, col_name] = f"{day_number} <br> {doctor_name}"
                day_number += 1

    return updated_df

# Generate colors for doctors
def assign_colors(doctors):
    # Use a set of visually distinct colors from Matplotlib
    palette = mcolors.TABLEAU_COLORS.values()  # 10 distinct colors
    
    # Cycle through the palette if there are more doctors than colors in the palette
    color_cycle = itertools.cycle(palette)
    
    out = {doctor: next(color_cycle) for doctor in doctors if doctor}
    out[""] = "#000000"  # Black color for empty cells
    return out

# Apply colors to cells
def style_cells(df, doctor_colors, show_day_numbers):
    def style_cell(val):
        if pd.isna(val):
            return ""  # No style for NaN cells
        if show_day_numbers:
            # Extract doctor name after day number
            try:
                _, doctor_name = val.split("<br>", 1)
            except ValueError:
                doctor_name = val  # Fallback if no newline exists
        else:
            doctor_name = val

        # Ensure doctor_name is a string
        doctor_name = str(doctor_name).strip()
        color = doctor_colors.get(doctor_name, "#ffffff")
        return f"background-color: {color}; color: white; text-align: center;"

    return df.style.map(style_cell)


# Front-End UI
st.title("Residents On-call Scheduling")

# Input Section
num_doctors = st.number_input("Number of doctors", min_value=1, max_value=30, step=1, value=3)
selected_month = st.date_input("Select month (chosen day doesn't make a difference)", format="DD/MM/YYYY")
month_and_year = selected_month.strftime("%B_%Y")
first_day_of_month = selected_month.replace(day=1)
starting_day = (first_day_of_month.weekday() + 1) % 7  # Sunday = 0, Monday = 1, ..., Saturday = 6
days_in_month = (first_day_of_month.replace(month=first_day_of_month.month % 12 + 1, day=1) - timedelta(days=1)).day

st.markdown(f"- Days in Month (_{month_and_year}_): :blue-background[{days_in_month}]")
st.markdown(f"- Starting day of the month: :blue-background[{first_day_of_month.strftime('%A')}]")

# Off-day Selection
st.subheader("Choose off-days for each doctor")
doctors_names = {np.nan: ""}
off_days = {}

off_days_options = [
    f"{i}/{first_day_of_month.month} - {datetime(first_day_of_month.year, first_day_of_month.month, i).strftime('%A')}"
    for i in range(1, days_in_month + 1)
]
for i in range(num_doctors):
    doctor_name = st.text_input(f"Doctor {i+1} Name", value=f"Doctor {i+1}")
    doctors_names[i] = doctor_name
    off_days[i] = st.multiselect(f"Off-days for {doctor_name}", options=off_days_options)


# Generate Schedule
if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = None  # Initialize session state for the schedule
    st.session_state.generation_time = None

if st.button("Generate Schedule"):
    st.write("Generating schedule...")
    # Convert off-days to disallowed pairs
    disallowed_pairs = [(int(day.split("/")[0]) - 1, doctor_index) for doctor_index, days in off_days.items() for day in days]
    
    start_time = time.time()
    
    st.session_state.schedule_df = generate_schedule(num_doctors, days_in_month, starting_day, disallowed_pairs)
    end_time = time.time()
    st.session_state.generation_time = end_time - start_time
    
if st.session_state.generation_time:
    st.write("Generated Schedule!")
    st.write(f"Total time taken for generating schedule: {st.session_state.generation_time:.2f} seconds")
    
st.divider()

if st.session_state.schedule_df is not None:
    schedule_df = st.session_state.schedule_df.copy()
    
    # Assign colors to doctors
    doctor_colors = assign_colors(doctors_names.values())
    
    # Checkbox to toggle displaying day numbers
    show_with_newlines = st.checkbox("Show with Days numbers", value=True)

    # Add day numbers if checkbox is selected
    if show_with_newlines:
        schedule_df = add_day_numbers(schedule_df, starting_day, days_in_month, doctors_names)
    else:
        schedule_df = schedule_df.replace(doctors_names)

    # Apply styles
    styled_schedule = style_cells(schedule_df, doctor_colors, show_with_newlines)
    st.markdown(styled_schedule.to_html(), unsafe_allow_html=True)
    
    # print counts of each doctor
    st.write("Number of On-calls scheduled for each doctor:")
    doctor_counts = st.session_state.schedule_df.stack().value_counts().to_dict()
    for doctor_index, count in doctor_counts.items():
        st.write(f"- {doctors_names[doctor_index]}: {count}")
    
    st.divider()


def prepare_export_df(df, start_day, total_days, doctors_names):
    export_data = []

    day_number = 1
    for row_idx, row in df.iterrows():
        for col_idx, col_name in enumerate(df.columns):
            if row_idx == 0 and col_idx < start_day:  # Skip initial empty slots
                continue
            if day_number > total_days:  # Stop when exceeding total days
                break
            
            doctor_index = row[col_name]
            if not pd.isna(doctor_index):  # Skip NaN entries
                export_data.append({
                    "Day Number": day_number,
                    "Day Name": col_name,
                    "Doctor's Name": doctors_names.get(doctor_index, ""),
                })
            day_number += 1

    return pd.DataFrame(export_data)

# Export to Excel and CSV
if st.button("Export to Excel"):
    if st.session_state.schedule_df is not None:
        export_df = prepare_export_df(
            st.session_state.schedule_df, starting_day, days_in_month, doctors_names
        )
        @st.cache_data
        def convert_df_to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            processed_data = output.getvalue()
            return processed_data
        
        excel_data = convert_df_to_excel(export_df)
        st.download_button(
            label="Download Schedule as Excel",
            data=excel_data,
            file_name=f"{month_and_year}_oncall_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if st.button("Export to CSV"):
    if st.session_state.schedule_df is not None:
        export_df = prepare_export_df(
            st.session_state.schedule_df, starting_day, days_in_month, doctors_names
        )
        @st.cache_data
        def convert_df_to_csv(df):
            return df.to_csv(index=False).encode('utf-8')
        
        csv_data = convert_df_to_csv(export_df)
        st.download_button(
            label="Download Schedule as CSV",
            data=csv_data,
            file_name=f"{month_and_year}_oncall_schedule.csv",
            mime="text/csv",
        )