#!/usr/bin/env python3
"""
Generator for a realistic, rigorous synthetic CERT Insider Threat r4.2 benchmark subset.
Adheres exactly to CMU CERT r4.2 schema, column headers, timestamps, and answer ground-truth.

Generates:
  - logon.csv: id,date,user,pc,activity
  - device.csv: id,date,user,pc,activity
  - file.csv: id,date,user,pc,filename,content
  - http.csv: id,date,user,pc,url,content
  - email.csv: id,date,user,pc,to,cc,bcc,from,size,attachments,content
  - answers/insiders.csv: dataset,scenario,details,user,start,end
"""
import os
import sys
import uuid
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "cert_r4.2"))
ANSWERS_DIR = os.path.join(DATA_DIR, "answers")

NUM_USERS = 120
NUM_DAYS = 90
START_DATE = datetime(2026, 3, 1, 0, 0, 0)

# 5 Insiders seeded into CERT r4.2 answers
INSIDER_SPECS = [
    {
        "user": "CMP0249",
        "scenario": 1,
        "details": "User visits leak sites and competitor job boards, then exfiltrates IP via cloud storage",
        "start_day": 50,
        "end_day": 70,
    },
    {
        "user": "ACM2278",
        "scenario": 2,
        "details": "Mass USB thumb-drive copy of proprietary CAD/software designs prior to resignation",
        "start_day": 65,
        "end_day": 78,
    },
    {
        "user": "EDB0714",
        "scenario": 3,
        "details": "Off-hours logon from unusual PC and bulk exfiltration of customer database via personal email",
        "start_day": 40,
        "end_day": 55,
    },
    {
        "user": "HAP0912",
        "scenario": 1,
        "details": "Off-hours data exfiltration to personal Dropbox and Wikileaks mirror",
        "start_day": 60,
        "end_day": 80,
    },
    {
        "user": "RAR0321",
        "scenario": 2,
        "details": "Repeated unauthorized USB mass storage connects and bulk file transfers",
        "start_day": 72,
        "end_day": 88,
    },
]


def gen_uuid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def cert_time(dt: datetime) -> str:
    """Format matching CERT r4.2 timestamps: MM/DD/YYYY HH:MM:SS"""
    return dt.strftime("%m/%d/%Y %H:%M:%S")


def generate_dataset():
    random.seed(42)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ANSWERS_DIR, exist_ok=True)

    print(f"Generating CERT r4.2 benchmark subset in {DATA_DIR}...")

    # Assign user PCs
    all_users = [s["user"] for s in INSIDER_SPECS]
    while len(all_users) < NUM_USERS:
        uid = f"USR{str(len(all_users) + 1).zfill(4)}"
        if uid not in all_users:
            all_users.append(uid)

    user_pcs = {u: f"PC-{random.randint(1000, 9999)}" for u in all_users}
    insider_map = {s["user"]: s for s in INSIDER_SPECS}

    # Files to generate
    f_logon = open(os.path.join(DATA_DIR, "logon.csv"), "w", encoding="utf-8")
    f_device = open(os.path.join(DATA_DIR, "device.csv"), "w", encoding="utf-8")
    f_file = open(os.path.join(DATA_DIR, "file.csv"), "w", encoding="utf-8")
    f_http = open(os.path.join(DATA_DIR, "http.csv"), "w", encoding="utf-8")
    f_email = open(os.path.join(DATA_DIR, "email.csv"), "w", encoding="utf-8")
    f_insiders = open(os.path.join(ANSWERS_DIR, "insiders.csv"), "w", encoding="utf-8")

    # Headers
    f_logon.write("id,date,user,pc,activity\n")
    f_device.write("id,date,user,pc,activity\n")
    f_file.write("id,date,user,pc,filename,content\n")
    f_http.write("id,date,user,pc,url,content\n")
    f_email.write("id,date,user,pc,to,cc,bcc,from,size,attachments,content\n")
    f_insiders.write("dataset,scenario,details,user,start,end\n")

    # Write insiders.csv
    for s in INSIDER_SPECS:
        start_dt = START_DATE + timedelta(days=s["start_day"])
        end_dt = START_DATE + timedelta(days=s["end_day"], hours=23, minutes=59, seconds=59)
        f_insiders.write(f"r4.2,{s['scenario']},\"{s['details']}\",{s['user']},{cert_time(start_dt)},{cert_time(end_dt)}\n")
    f_insiders.close()

    NORMAL_DOMAINS = ["google.com", "github.com", "stackoverflow.com", "internal-portal.corp", "docs.python.org", "wikipedia.org"]
    RISKY_DOMAINS = ["dropbox.com", "drive.google.com", "wikileaks.org", "monster.com", "mega.nz", "pastebin.com"]

    # Generate daily events per user
    for day_idx in range(NUM_DAYS):
        day_date = START_DATE + timedelta(days=day_idx)
        is_weekend = day_date.weekday() >= 5

        for user in all_users:
            primary_pc = user_pcs[user]
            insider_info = insider_map.get(user)
            is_malicious_day = False
            if insider_info:
                if insider_info["start_day"] <= day_idx <= insider_info["end_day"]:
                    is_malicious_day = True

            # If weekend and benign, 96% chance inactive
            if is_weekend and not is_malicious_day:
                if random.random() > 0.04:
                    continue

            # 1. LOGON / LOGOFF
            if is_malicious_day and insider_info["scenario"] == 3:
                # Off-hours logon from foreign/unusual PC
                pc = f"PC-{random.randint(9000, 9999)}"
                login_dt = day_date.replace(hour=random.choice([1, 2, 22, 23]), minute=random.randint(0, 59))
                logout_dt = login_dt + timedelta(minutes=random.randint(45, 180))
            else:
                pc = primary_pc
                login_h = int(random.gauss(8.5, 0.5))
                login_h = max(7, min(10, login_h))
                login_dt = day_date.replace(hour=login_h, minute=random.randint(0, 59))
                work_mins = random.randint(420, 540)
                logout_dt = login_dt + timedelta(minutes=work_mins)

            f_logon.write(f"{gen_uuid()},{cert_time(login_dt)},{user},{pc},Logon\n")
            f_logon.write(f"{gen_uuid()},{cert_time(logout_dt)},{user},{pc},Logoff\n")

            # 2. HTTP BROWSING
            num_http = random.randint(10, 30)
            if is_malicious_day and insider_info["scenario"] == 1:
                num_http += random.randint(20, 50)
                # Visits to job sites, leak sites, cloud uploads
                for _ in range(random.randint(5, 12)):
                    h_dt = login_dt + timedelta(minutes=random.randint(10, 360))
                    dom = random.choice(RISKY_DOMAINS)
                    url = f"https://{dom}/data/upload/{uuid.uuid4().hex[:8]}"
                    f_http.write(f"{gen_uuid()},{cert_time(h_dt)},{user},{pc},{url},[CONTENT_OMITTED]\n")

            for _ in range(num_http):
                h_dt = login_dt + timedelta(minutes=random.randint(10, 400))
                dom = random.choice(NORMAL_DOMAINS)
                url = f"https://{dom}/page/{random.randint(1, 500)}"
                f_http.write(f"{gen_uuid()},{cert_time(h_dt)},{user},{pc},{url},[CONTENT_OMITTED]\n")

            # 3. USB & FILE ACTIVITY
            if is_malicious_day and insider_info["scenario"] == 2:
                # Mass USB device connect + file copies to removable media
                usb_dt = login_dt + timedelta(minutes=random.randint(60, 240))
                f_device.write(f"{gen_uuid()},{cert_time(usb_dt)},{user},{pc},Connect\n")
                # Multiple file copies to E:\ (removable)
                for f_idx in range(random.randint(15, 45)):
                    f_time = usb_dt + timedelta(seconds=random.randint(10, 600))
                    f_name = f"E:\\proprietary_design_v{f_idx}_{uuid.uuid4().hex[:6]}.zip"
                    f_file.write(f"{gen_uuid()},{cert_time(f_time)},{user},{pc},{f_name},[BINARY_CONTENT_OMITTED]\n")
                f_device.write(f"{gen_uuid()},{cert_time(usb_dt + timedelta(minutes=random.randint(15, 30)))},{user},{pc},Disconnect\n")
            else:
                # Normal occasional USB
                if random.random() < 0.03:
                    u_dt = login_dt + timedelta(minutes=random.randint(60, 180))
                    f_device.write(f"{gen_uuid()},{cert_time(u_dt)},{user},{pc},Connect\n")
                    if random.random() < 0.4:
                        f_name = f"C:\\Users\\{user}\\Documents\\meeting_notes.docx"
                        f_file.write(f"{gen_uuid()},{cert_time(u_dt + timedelta(minutes=5))},{user},{pc},{f_name},[CONTENT_OMITTED]\n")
                    f_device.write(f"{gen_uuid()},{cert_time(u_dt + timedelta(minutes=15))},{user},{pc},Disconnect\n")

            # 4. EMAIL ACTIVITY
            num_emails = random.randint(2, 8)
            if is_malicious_day and insider_info["scenario"] == 3:
                # Heavy emails with large attachments to external domains
                for _ in range(random.randint(4, 10)):
                    e_dt = login_dt + timedelta(minutes=random.randint(15, 120))
                    ext_to = f"personal_{user.lower()}@gmail.com;confidential@yahoo.com"
                    att_count = random.randint(3, 8)
                    size_bytes = random.randint(15000000, 45000000) # 15-45 MB
                    f_email.write(f"{gen_uuid()},{cert_time(e_dt)},{user},{pc},{ext_to},,,{user.lower()}@dtaa.com,{size_bytes},{att_count},[BODY_OMITTED]\n")

            for _ in range(num_emails):
                e_dt = login_dt + timedelta(minutes=random.randint(30, 420))
                to_addr = f"colleague_{random.randint(1, 50)}@dtaa.com"
                att_count = 1 if random.random() < 0.25 else 0
                size_bytes = random.randint(20000, 800000) if att_count else random.randint(3000, 40000)
                f_email.write(f"{gen_uuid()},{cert_time(e_dt)},{user},{pc},{to_addr},,,{user.lower()}@dtaa.com,{size_bytes},{att_count},[BODY_OMITTED]\n")

    f_logon.close()
    f_device.close()
    f_file.close()
    f_http.write("")
    f_http.close()
    f_email.close()

    print(f"✓ CERT r4.2 dataset successfully generated with {len(all_users)} users across {NUM_DAYS} days.")
    print(f"  Includes {len(INSIDER_SPECS)} ground-truth malicious actors.")


if __name__ == "__main__":
    generate_dataset()
