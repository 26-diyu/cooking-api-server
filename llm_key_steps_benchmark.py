import datetime
import time
from urllib.parse import quote_plus

import psycopg
from psycopg.rows import dict_row

from recipe_language_model import RecipeLLM
from relational_database import RelationalDatabase


class LLMKeySteps:
    def __init__(self):
        password = "recipe@123"
        encoded_password = quote_plus(password)
        self.DB_URL = f"postgresql://postgres:{encoded_password}@localhost:5432/test"
        self.recipe_llm = RecipeLLM()
        self.relational_database = RelationalDatabase.get_instance()

    def benchmark(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fpw = open(f"./benchmark/key-steps-benchmark-{timestamp}.csv", "w")
        fpw.write("video_id,num_steps,length,output_num_steps,output_length,time_taken\n")
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
                    if row['transcript']['video_id'] != "JkYwSddTdew":
                        continue
                    print(f"ID: {row['id']} | VideoID: {row['transcript']['video_id']} | Transcript: {row['transcript']}")
                    transcript = self.relational_database.get_transcript(video_id=row['transcript']['video_id'])
                    print(transcript)
                    transcript_text = ""
                    for timestamp_text in transcript.get("timestamp_texts", []):
                        timestamp = timestamp_text.get('timestamp', 0.0)
                        text = timestamp_text.get('text', "")
                        transcript_text += f"[{timestamp:.2f}s]: {text}\n"
                    print(transcript_text)
                    start_time = time.time()
                    recipe_content = self.recipe_llm.extract_key_steps(transcript)
                    end_time = time.time()
                    print(recipe_content)
                    key_steps = ""
                    for recipe_step in recipe_content.steps:
                        key_steps += f"{recipe_step.timestamp}: {recipe_step.description}\n"
                    print("transcript number of steps:", len(transcript.get("timestamp_texts", [])))
                    print("number of key steps:", len(recipe_content.steps))
                    print("len(transcript_text)", len(transcript_text))
                    print("len(key_steps):", len(key_steps))
                    print("Time elapsed (seconds)", end_time - start_time)
                    fpw.write("%s,%d,%d,%d,%d,%.0f\n" % (row['transcript']['video_id'],
                                                                            len(transcript.get("timestamp_texts", [])),
                                                                            len(transcript_text), len(recipe_content.steps),
                                                                            len(key_steps), (end_time - start_time)))
                    #break
        fpw.close()

if __name__ == "__main__":
    llm_key_steps = LLMKeySteps()
    llm_key_steps.benchmark()