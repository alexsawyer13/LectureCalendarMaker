from dataclasses import dataclass
import string
import datetime
import unicodedata

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

# ----- Globals -----

start_date = datetime.datetime(2022, 10, 3) # Week 0 Monday

weekday_to_int = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}

base_url = "https://www3.physics.ox.ac.uk/lectures/"
URL = "https://www3.physics.ox.ac.uk/lectures/timetable.aspx?term=Michaelmas&year=2022&course=1physics"

# ----- Dataclasses -----

@dataclass
class HrefInfo:
    info: string

@dataclass
class Activity:
    start: datetime.datetime
    end: datetime.datetime
    name: string
    href: string = ""

    def __init__(self, start, end, name, href):
        self.start = start
        self.end = end
        self.name = unicodedata.normalize("NFKC", name.strip())
        self.href = unicodedata.normalize("NFKC", href.strip())

    def print(self, href = False):
        print(self.start.strftime("%H:%M:%S") + " - " + self.end.strftime("%H:%M:%S") + ": " + self.name)
        if href:
            print(self.href)

    # Subject, Start Date, Start Time, End Date, End Time
    def csv(self):
        return self.name + "," + self.start.strftime("%d/%m/%Y") + "," + self.start.strftime("%H:%M:%S") + "," + \
            self.end.strftime("%d/%m/%Y") + "," + self.end.strftime("%H:%M:%S") + ",\"" + parse_href(self.href).info + "\""

@dataclass
class Day:
    activities: list[Activity]
    midnight: datetime.datetime

    def time(self, hours: int = 0, minutes: int = 0, seconds: int = 0) -> datetime.timedelta:
        return self.midnight + datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

    def print(self, href = False):
        print(self.midnight.strftime("%A %d/%m/%Y"))
        for activity in self.activities:
            activity.print()

    def compress(self):
        # Combine adjacent activities and remove duplicates
        num_activities = len(self.activities)
        for i in range(1, num_activities):
            curr: Activity = self.activities[i]
            prev: Activity = self.activities[i-1]

            # Activities are identical
            if curr == prev:
                # Remove prev
                self.activities[i-1] = None
                continue
            
            # Activities are the same type
            if curr.name == prev.name and curr.href == prev.href:
                # Activities overlap
                if prev.end == curr.start:
                    # Combine into one and remove prev
                    self.activities[i].start = prev.start
                    self.activities[i-1] = None

        # Remove the nones
        self.activities = [x for x in self.activities if x is not None]

    def csv(self):
        csv = ""
        for activity in self.activities:
            csv += (activity.csv() + "\n")
        return csv

# ----- Functions -----

def get_datetime(week: int, day: string) -> datetime.datetime:
    return start_date + datetime.timedelta(weekday_to_int[day.lower()] + int(week) * 7)

def get_day_from_row(row):
    columns = row.find_all("td")

    raw_week = int(columns[0].text)
    raw_day = columns[1].text
    day = Day([], get_datetime(raw_week, raw_day))

    if (len(columns[2].text.strip()) > 0): day.activities.append(Activity(day.time(9), day.time(10), columns[2].text, columns[2].find("a").get("href")))
    if (len(columns[3].text.strip()) > 0): day.activities.append(Activity(day.time(10), day.time(11), columns[3].text, columns[3].find("a").get("href")))
    if (len(columns[4].text.strip()) > 0): day.activities.append(Activity(day.time(11), day.time(12), columns[4].text, columns[4].find("a").get("href")))
    if (len(columns[5].text.strip()) > 0): day.activities.append(Activity(day.time(12), day.time(13), columns[5].text, columns[5].find("a").get("href")))

    afternoon_activity_cell = columns[6]

    # Skip afternoon activities if cell is empty
    if (len(afternoon_activity_cell.text.strip()) > 0):
        tokens = afternoon_activity_cell.prettify().split('\n')[1:-1]

        current_tokens = []
        afternoon_activities = []

        for token in tokens:
            token = token.strip()

            if (token == "<br/>"):
                afternoon_activities.append(current_tokens)
                current_tokens = []

            else:
                # print(token)
                current_tokens.append(token)

        if len(current_tokens) > 0:
            afternoon_activities.append(current_tokens)

        for activity in afternoon_activities:
            (start_time, end_time) = activity[0].split(' - ')
            start_time = int(float(start_time))
            end_time = int(float(end_time))
            name = activity[2]
            href = activity[1][9:-2].replace('&amp;', '&')
            day.activities.append(Activity(day.time(start_time), day.time(end_time), name, href))

    day.compress()
    return day

# ----- Main -----

page = requests.get(URL)
if (not page):
    print("Couldn't get lecture page, are you connected to the oxford vpn?")
    exit()

soup = BeautifulSoup(page.content, "html.parser")
table_rows = soup.find(id="mainContent").find("table").find_all("tr")

days = [get_day_from_row(row) for row in table_rows[1:]]

# [day.print() for day in days]

href_info_cache = {}

def parse_href(href: string):
    if href in href_info_cache:
        return href_info_cache[href]

    print("PARSING HREF " + href)

    href_url = base_url + href
    page = requests.get(href_url)
    soup = BeautifulSoup(page.content, "html.parser")

    info = ""

    for tag in soup.find(id="overviewContent"):
        info += (tag.text + "\n")

    info += "\n"

    info += (soup.find(id="materialsContent2").text + "\n\n")

    info += (soup.find(id="materialsContent3").text + "\n")

    href_info_cache[href] = HrefInfo(info)
    return href_info_cache[href]


day = days[-6]
href = parse_href(day.activities[0].href)

csv = 'Subject,Start Date,Start Time,End Date,End Time,Description\n'
for day in days:
    csv += day.csv()
open("out.csv", "w").write(csv.strip("\n"))