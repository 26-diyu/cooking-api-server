import numpy as np
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate


# -------------------------------------------------------------------
# 1. Define Intent Schema & Pydantic Model
# -------------------------------------------------------------------
class IntentEnum(str, Enum):
    GENERATE_RECIPE = "generate_recipe"
    EXTRACT_INGREDIENTS = "extract_ingredients"
    UNKNOWN = "unknown"


class IntentClassification(BaseModel):
    intent: IntentEnum = Field(
        description="The classified intent of the user request."
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief explanation for the classification."
    )


# -------------------------------------------------------------------
# 2. Hybrid Intent Classifier Implementation
# -------------------------------------------------------------------
class HybridIntentClassifier:
    def __init__(
            self,
            model_name: str = "llama3.2",
            embedding_model_name: str = "mxbai-embed-large",
            similarity_threshold: float = 0.85
    ):
        self.similarity_threshold = similarity_threshold

        # Initialize Embeddings & LLM via LangChain Ollama integration
        self.embeddings = OllamaEmbeddings(model=embedding_model_name)

        # Setup structured output model
        llm = ChatOllama(model=model_name, temperature=0.0)
        self.structured_llm = llm.with_structured_output(IntentClassification)

        # Reference dataset for Vector Search Layer
        self.reference_examples: Dict[IntentEnum, List[str]] = {
            IntentEnum.GENERATE_RECIPE: [
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. https://www.youtube.com/watch?v=TwrsUrYiRsA",
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. Could you please generate recipe ouf this youtube video https://www.youtube.com/watch?v=TwrsUrYiRsA ?",
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. Yes, for this youtube video https://www.youtube.com/watch?v=TwrsUrYiRsA",
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. Youtube video link https://www.youtube.com/watch?v=TwrsUrYiRsA",
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. Youtube video https://www.youtube.com/watch?v=TwrsUrYiRsA",
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. video https://www.youtube.com/watch?v=TwrsUrYiRsA",
                "Hi! Send me a YouTube cooking video link to generate step by step recipe. video url https://www.youtube.com/watch?v=TwrsUrYiRsA"
            ],
            IntentEnum.EXTRACT_INGREDIENTS: [
                "Would you like to list the ingredients for the recipe? Yes please",
                "Would you like to list the ingredients for the recipe? Yes, please list the ingredients",
                "Would you like to list the ingredients for the recipe? Yes, could you please list the ingredients ?",
                "Would you like to list the ingredients for the recipe? Yes, I would like to list the ingredients ",
            ]
        }

        # Pre-compute and cache vector embeddings for reference dataset
        self.example_embeddings = self._index_reference_examples()

    def _index_reference_examples(self) -> List[dict]:
        """Encodes all pre-defined reference queries into vector space."""
        indexed = []
        for intent, phrases in self.reference_examples.items():
            for phrase in phrases:
                vector = self.embeddings.embed_query(phrase)
                indexed.append({
                    "intent": intent,
                    "phrase": phrase,
                    "vector": np.array(vector, dtype=np.float32)
                })
        return indexed

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculates vector cosine similarity."""
        return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))

    def _classify_via_vector_search(self, user_query: str) -> Optional[IntentClassification]:
        """Layer 1: Fast Vector Similarity Check"""
        query_vector = np.array(self.embeddings.embed_query(user_query), dtype=np.float32)

        best_match = None
        highest_sim = -1.0

        for item in self.example_embeddings:
            sim = self._cosine_similarity(query_vector, item["vector"])
            if sim > highest_sim:
                highest_sim = sim
                best_match = item["intent"]

        # If similarity meets high confidence threshold, bypass LLM
        if highest_sim >= self.similarity_threshold and best_match:
            return IntentClassification(
                intent=best_match,
                confidence=round(highest_sim, 2),
                reasoning=f"Matched via fast vector search (similarity: {round(highest_sim, 2)})"
            )

        return None

    def _classify_via_llm(self, user_query: str) -> IntentClassification:
        """Layer 2: Fallback to LLM Structured Output"""
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert NLP classifier for a cooking application.\n"
                "Determine if the user request belongs to 'generate_recipe' or 'extract_ingredients'.\n\n"
                "- generate_recipe: User wants step-by-step instructions or cooking methods.\n"
                "- extract_ingredients: User only wants the list of components, shopping list, or items needed.\n"
                "- unknown: Use this if the query is totally unrelated to cooking or recipes."
            ),
            ("user", "{input}")
        ])

        chain = prompt | self.structured_llm
        result = chain.invoke({"input": user_query})
        return result

    def classify(self, user_query: str) -> IntentClassification:
        """Runs the hybrid classification pipeline."""
        # 1. Try Layer 1 (Embeddings)
        fast_result = self._classify_via_vector_search(user_query)
        if fast_result:
            return fast_result

        # 2. Fallback to Layer 2 (Structured LLM Inference)
        return self._classify_via_llm(user_query)


# -------------------------------------------------------------------
# 3. Test Cases & Usage
# -------------------------------------------------------------------
if __name__ == "__main__":
    classifier = HybridIntentClassifier()

    test_queries = [
        "Hi! Send me a YouTube cooking video link to generate step by step recipe. https://www.youtube.com/watch?v=TwrsUrYiRsA",
        "Hi! Send me a YouTube cooking video link to generate step by step recipe. Youtube video URL https://www.youtube.com/watch?v=TwrsUrYiRsA",
        "Would you like to list the ingredients for the recipe? Yes, I would like to",
        "Would you like to list the ingredients for the recipe? Yes",
        "Would you like to list the ingredients for the recipe? Yes, I would",
        "Would you like to list the ingredients for the recipe? Could you please extract the ingredients?",
    ]

    for query in test_queries:
        print(f"\nUser Query: '{query}'")
        result = classifier.classify(query)
        print(f"-> Intent:     {result.intent.value}")
        print(f"-> Confidence: {result.confidence}")
        print(f"-> Reasoning:  {result.reasoning}")