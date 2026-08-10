import datetime
import time
from urllib.parse import quote_plus

import psycopg
from psycopg.rows import dict_row
import yt_dlp

from recipe_language_model import RecipeLLM
from relational_database import RelationalDatabase


class LLMTitle:
    def __init__(self):
        password = "recipe@123"
        encoded_password = quote_plus(password)
        self.DB_URL = f"postgresql://postgres:{encoded_password}@localhost:5432/test"
        self.recipe_llm = RecipeLLM()
        self.relational_database = RelationalDatabase.get_instance()

    def get_video_description(self, video_url) -> str:
        if video_url is None or video_url == "":
            return ""
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_description = info.get('description', 'video')
            print("video_description:", video_description)
            return video_description

    def benchmark(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fpw = open(f"./benchmark/title-benchmark-{timestamp}.csv", "w")
        fpw.write("video_id,length,title_length,time_taken\n")
        with psycopg.connect(self.DB_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # --- 1. SELECT Query (Fetching Data) ---
                query = """
                    SELECT id, transcript 
                    FROM public.videotranscript;
                """
                cur.execute(query)  # Pass arguments as a tuple
                # Fetch all rows matching the query
                rows = cur.fetchall()
                print("--- SELECT Results ---")
                for row in rows:
                    print(f"ID: {row['id']} | VideoID: {row['transcript']['video_id']} | Transcript: {row['transcript']}")
                    video_id = row['transcript']['video_id']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    video_description = self.get_video_description(video_url)
                    if video_description and video_description != "" and len(video_description) > 100:
                        text = video_description
                    else:
                        video_id = video_url.split("v=")[-1]
                        transcript = self.relational_database.get_transcript(video_id=video_id)
                        transcript_text = ""
                        for timestamp_text in transcript["timestamp_texts"]:
                            transcript_text += timestamp_text["text"] + "\n"
                        #print("transcript text: ", transcript_text)
                        text = transcript_text
                    print("text:", text)
                    start_time = time.time()
                    recipe_title = self.recipe_llm.generate_title(video_url)
                    end_time = time.time()
                    print(recipe_title)
                    print("len(text)", len(text))
                    print("len(recipe_title):", len(recipe_title))
                    print("Time elapsed (seconds)", end_time - start_time)
                    fpw.write("%s,%d,%d,%.0f\n" % (video_id,len(text), len(recipe_title), (end_time - start_time)))
                    #break
        fpw.close()

if __name__ == "__main__":
    llm_title = LLMTitle()
    llm_title.benchmark()