import traceback
import yt_dlp

from data_model import Transcript, RecipeContent, RecipeStep
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from relational_database import RelationalDatabase

class RecipeLLM:
    def __init__(self):
        self.llm = ChatOllama(model="llama3.2", temperature=0)
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

    def extract_key_steps(self, transcript:Transcript) -> RecipeContent:
        timestamp_text_dict = {}
        transcript_text = ""
        for timestamp_text in transcript.get("timestamp_texts", []):
            timestamp = timestamp_text.get('timestamp', 0.0)
            text = timestamp_text.get('text', "")
            transcript_text += f"[{timestamp:.2f}s]: {text}\n"
            timestamp_text_dict[timestamp] = text
        print(transcript_text)
        system_prompt = """
        You are an expert culinary assistant. Your goal is to parse a raw video transcript and extract the definitive, step-by-step cooking instructions for a recipe.

        Follow these strict guidelines:
        1. FOCUS ON ACTIONS: Extract steps that involve physical cooking actions (e.g., heating a pan, adding ingredients, adjusting flame, blending, plating).
        2. FILTER OUT NOISE: Ignore conversational filler, background talk, anecdotes, or repetitive instructions. 
        3. PRESERVE TIMESTAMPS: Keep the exact timestamp provided in the transcript for each step so users can reference the video.

        ### INSTRUCTIONS FOR YOUR OUTPUT:
        You must respond ONLY with a valid JSON object. Do not include any conversational filler, markdown formatting (like ```json), or text outside the JSON object. 

        The JSON structure must match this exactly:
        {{
          "description": "One sentence description about the steps",
          "steps": "The list of steps with each step should follow this format: ["Timestamp", "Step-description"]"
        }}
        """
        # 2. Define the prompt structure
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Here is the raw transcript to analyze:\n\n{transcript}")
        ])
        # Chain them together
        chain = prompt | self.llm | JsonOutputParser()
        response = None
        counter = 0
        while response is None and counter < 3:
            # Run the chain
            response = chain.invoke({"transcript": transcript_text})
            counter += 1

        if response is None:
            return RecipeContent(description="", steps=[])

        print(response)
        recipe_content = RecipeContent(description=response['description'], steps=[])
        print("KEY STEPS")
        output_dir = f'data/{transcript.get("video_id")}/key-frames'
        timestamps = []
        for timestamp_description in response["steps"]:
            try:
                if len(timestamp_description) == 2:
                    seconds = timestamp_description[0]
                    step_description = timestamp_description[1]
                    seconds = float(seconds.strip().strip('"').rstrip('s'))
                    timestamps.append(seconds)
                    print(f"seconds: {seconds}, step_description: {step_description}")
                    recipe_step = RecipeStep(timestamp=seconds, description=step_description, image_url=f"{output_dir}/frame_at_{seconds}s.jpg")
                    recipe_content.steps.append(recipe_step)
            except ValueError:
                print(f"Skipping invalid timestamp: {timestamp_description}")
        return recipe_content

    def generate_title(self, video_url) -> str:
        print("Generating title ...")
        video_description = self.get_video_description(video_url)
        if video_description and video_description != "" and len(video_description) > 100:
            text = video_description
        else:
            video_id = video_url.split("v=")[-1]
            transcript = self.relational_database.get_transcript(video_id=video_id)
            transcript_text = ""
            for timestamp_text in transcript["timestamp_texts"]:
                transcript_text += timestamp_text["text"] + "\n"
            print("transcript text: ", transcript_text)
            text = transcript_text
        system_prompt = """
                You are an expert culinary assistant. Your goal is to parse a raw video transcript or a video description and come up with the definition or the title for the recipe.
                Follow these strict guidelines:
                1. LENGTH OF THE TITLE: MAXIMUM 4 WORDS UPTO 50 characters
                ### INSTRUCTIONS FOR YOUR OUTPUT:
                You must respond ONLY with a valid JSON object. Do not include any conversational filler, markdown formatting (like ```json), or text outside the JSON object. 

                The JSON structure must match this exactly:
                {{
                  "title": "The title of the recipe up to 4 words."
                }}
                """
        # 2. Define the prompt structure
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Here is the raw transcript or description to analyze:\n\n{text}")
        ])
        try:
            llm = ChatOllama(model="llama3.2", temperature=0)
            # Chain them together
            chain = prompt | llm | JsonOutputParser()
            response = chain.invoke({"text": text})
            print("response:", response)
            return response["title"]
        except:
            print("Something went wrong while generating the title")
            traceback.print_exc()
            return ""

    def extract_ingredients(self, video_url) -> list:
        video_description = self.get_video_description(video_url)
        if video_description and video_description.lower().find("ingredient") != -1:
            text = video_description
        else:
            video_id = video_url.split("v=")[-1]
            transcript = self.relational_database.get_transcript(video_id=video_id)
            transcript_text = ""
            for timestamp_text in transcript["timestamp_texts"]:
                transcript_text += timestamp_text["text"] + "\n"
            print("transcript text: ", transcript_text)
            text = transcript_text
        system_prompt = """
                    You are an expert culinary assistant. Your goal is to parse a text and come up with the ingredients with the quantity for the recipe.
                    Follow these strict guidelines:
                    1. INGREDIENTS ACCOMPANY BY THE QUANTITY e.g., 2 tbsp butter, 2 cups milk
                    ### INSTRUCTIONS FOR YOUR OUTPUT:
                    You must respond ONLY with a valid JSON object. Do not include any conversational filler, markdown formatting (like ```json), or text outside the JSON object. 

                    The JSON structure must match this exactly:
                    {{
                      "ingredients": ["ingredient1", "ingredient2", "ingredient3"...]
                    }}
                    """
        # 2. Define the prompt structure
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Here is the text to analyze:\n\n{text}")
        ])
        llm = ChatOllama(model="llama3.2", temperature=0)
        # Chain them together
        chain = prompt | llm | JsonOutputParser()
        response = chain.invoke({"text": text})
        print(response)
        return response["ingredients"]

if __name__ == "__main__":
    video_id = "5de_BWIBnGk"
    relational_database = RelationalDatabase.get_instance()
    transcript_response = relational_database.get_transcript(video_id=video_id)
    print(transcript_response)
    recipe_llm = RecipeLLM()
    #recipe_llm.extract_key_steps(transcript_response)
    video_url = "https://www.youtube.com/watch?v=EbpSHiRRK7I"
    print("title")
    print(recipe_llm.generate_title(video_url))
    print("ingredients")
    print(recipe_llm.extract_ingredients(video_url))
