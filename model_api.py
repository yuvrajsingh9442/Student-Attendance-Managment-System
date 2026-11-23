import json
import os
import re
from pathlib import Path

DATA_FILE = Path(__file__).with_name("students.json")


def load_data():
    if not DATA_FILE.exists():
        default_data = {
            "total_days": 5,
            "students": [
                {
                    "name": "Aarav Sharma",
                    "roll": 101,
                    "attendance": ["P", "P", "P", "P", "P"]
                },
                {
                    "name": "Yuvraj",
                    "roll": 102,
                    "attendance": ["P", "A", "P", "P", "P"]
                },
                {
                    "name": "Priya Singh",
                    "roll": 103,
                    "attendance": ["A", "P", "P", "P", "A"]
                }
            ]
        }
        save_data(default_data)
        return default_data

    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if data.get("total_days") != 5:
        raise ValueError("This project expects exactly 5 attendance days.")

    for student in data.get("students", []):
        if len(student.get("attendance", [])) != data["total_days"]:
            raise ValueError(f"Invalid attendance record for student {student.get('name')}.")
        if any(x not in ("P", "A") for x in student["attendance"]):
            raise ValueError("Attendance must contain only P or A.")

    return data


def save_data(data):
    temp_file = DATA_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
    temp_file.replace(DATA_FILE)


def calculate_attendance(student, total_days):
    present = student["attendance"].count("P")
    percentage = round(present / total_days * 100, 2)

    return {
        "name": student["name"],
        "roll": student["roll"],
        "present_days": present,
        "absent_days": total_days - present,
        "total_days": total_days,
        "attendance_percentage": percentage
    }


def get_student(data, roll):
    for student in data["students"]:
        if student["roll"] == roll:
            return student
    raise ValueError(f"Student with roll number {roll} was not found.")


def mark_attendance(roll, day, status):
    data = load_data()

    if not 1 <= day <= data["total_days"]:
        raise ValueError("Day must be between 1 and 5.")

    status = status.upper().strip()
    if status in ("PRESENT", "P"):
        status = "P"
    elif status in ("ABSENT", "A"):
        status = "A"
    else:
        raise ValueError("Status must be P (Present) or A (Absent).")

    student = get_student(data, roll)
    old_status = student["attendance"][day - 1]
    student["attendance"][day - 1] = status

    save_data(data)

    return {
        "message": "Attendance updated successfully",
        "roll": roll,
        "day": day,
        "previous_status": old_status,
        "new_status": status,
        "attendance": calculate_attendance(student, data["total_days"])
    }


def get_attendance(roll):
    data = load_data()
    student = get_student(data, roll)
    return calculate_attendance(student, data["total_days"])


def attendance_report():
    data = load_data()
    return [
        calculate_attendance(student, data["total_days"])
        for student in data["students"]
    ]


def print_menu():
    print("\n" + "=" * 50)
    print("         AI ATTENDANCE MANAGEMENT SYSTEM          ")
    print("=" * 50)
    print("  [1] View All Students Report")
    print("  [2] Check Attendance by Roll No (e.g. 102)")
    print("  [3] Mark Attendance (Present / Absent)")
    print("  [4] Help / Available Commands")
    print("  [5] Exit")
    print("=" * 50)


def interpret_with_huggingface(command):
    """Optional AI command interpretation when HF_TOKEN is provided."""
    from huggingface_hub import InferenceClient

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN not set.")

    client = InferenceClient(api_key=token, provider="auto")
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Convert the user's attendance request into one JSON object only. "
                    "Allowed actions: mark, report, report_all. "
                    "For mark: return action, roll, day, status (P or A). "
                    "For report: return action, roll. "
                    "For report_all: return action only."
                )
            },
            {"role": "user", "content": command}
        ],
        temperature=0
    )
    return json.loads(response.choices[0].message.content)


def execute_ai_command(command):
    action = interpret_with_huggingface(command)
    if not isinstance(action, dict):
        raise ValueError("AI returned an invalid format.")

    name = action.get("action")
    if name == "mark":
        return mark_attendance(int(action["roll"]), int(action["day"]), action["status"])
    if name == "report":
        return get_attendance(int(action["roll"]))
    if name == "report_all":
        return attendance_report()

    raise ValueError("Unsupported AI action.")


def handle_command(command):
    cmd = command.strip()
    if not cmd:
        return None

    # Option 1 or report all
    if cmd.lower() in ("1", "report all", "all", "report", "view all", "list"):
        return attendance_report()

    # Option 5 or exit
    if cmd.lower() in ("5", "exit", "quit", "q"):
        return "exit"

    # Option 4 or help
    if cmd.lower() in ("4", "help", "?", "menu"):
        print_menu()
        return {"info": "Options: 1=View All, 2=Check Roll, 3=Mark Attendance, 5=Exit"}

    # Option 2 alone (prompt for roll)
    if cmd == "2":
        roll_input = input("Enter Student Roll Number (e.g. 102): ").strip()
        num_match = re.search(r"\d+", roll_input)
        if not num_match:
            raise ValueError("Please provide a valid numeric roll number.")
        return get_attendance(int(num_match.group(0)))

    # Option 3 alone (interactive mark)
    if cmd == "3":
        roll_input = input("Enter Roll Number (e.g. 102): ").strip()
        roll_num = int(re.search(r"\d+", roll_input).group(0))
        day_num = int(input("Enter Day (1-5): ").strip())
        status_in = input("Enter Status (P for Present / A for Absent): ").strip()
        return mark_attendance(roll_num, day_num, status_in)

    # Mark command pattern: "mark roll 102 absent day 3", "mark 102 P 2", etc.
    match = re.fullmatch(
        r"mark\s+(?:roll\s*(?:no\.?)?\s*)?(\d+)\s+(present|absent|p|a)(?:\s+day|\s+d)?\s*(\d+)",
        cmd,
        re.IGNORECASE
    )
    if match:
        roll = int(match.group(1))
        status = match.group(2)
        day = int(match.group(3))
        return mark_attendance(roll, day, status)

    # Roll check pattern: "roll 102", "roll no 102", "report roll 102", or standalone number "102"
    match = re.fullmatch(
        r"(?:(?:report|check)\s+)?(?:roll\s*(?:no\.?|number)?\s*)?(\d+)",
        cmd,
        re.IGNORECASE
    )
    if match:
        return get_attendance(int(match.group(1)))

    # Fallback to AI if HF_TOKEN is configured
    if os.environ.get("HF_TOKEN"):
        try:
            return execute_ai_command(cmd)
        except Exception:
            pass

    raise ValueError(
        f"Input '{command}' was not recognized.\n"
        "Options:\n"
        "  1 -> View All Students Report\n"
        "  2 -> Check Student Attendance (or type 'roll no 102')\n"
        "  3 -> Mark Attendance (or type 'mark roll 102 absent day 3')\n"
        "  5 -> Exit"
    )


if __name__ == "__main__":
    print_menu()

    while True:
        try:
            command = input("\nEnter choice (1-5) or command: ").strip()
            if not command:
                continue

            result = handle_command(command)
            if result == "exit":
                print("Exiting Attendance System. Goodbye!")
                break

            if result is not None:
                print(json.dumps(result, indent=2))

        except Exception as error:
            print(json.dumps({
                "error": str(error),
                "data_updated": False
            }, indent=2))
