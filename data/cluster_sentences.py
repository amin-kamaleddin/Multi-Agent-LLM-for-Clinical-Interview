import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import seaborn as sns
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv
import time
from typing import List, Dict
import json

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Load .env file from one level above
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)




class ConversationClusterer:
    def __init__(self, csv_file_path, text_column='input', openai_api_key=None):
        """
        Initialize the conversation clusterer with LLM-based depression classification

        Args:
            csv_file_path (str): Path to the CSV file
            text_column (str): Name of the text column
            openai_api_key (str): OpenAI API key for LLM classification
        """
        self.csv_file_path = csv_file_path
        self.text_column = text_column
        self.df = None
        self.embeddings = None
        self.kmeans = None
        self.clusters = None

        # Set up LLM for depression classification
        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        elif not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found. Please set it in .env or pass as argument.")

        self.llm = None
        self.depression_chain = None
        self.setup_depression_classifier()

    def setup_depression_classifier(self):
        """Set up the LLM chain for depression classification"""
        try:
            # Initialize the LLM (using GPT-3.5-turbo for cost efficiency)
            self.llm = ChatOpenAI(
                model_name="gpt-4o-mini",
                temperature=0,  # Low temperature for consistent classification
            )

            # Create the prompt template for depression classification
            depression_prompt = PromptTemplate(
                input_variables=["conversation_text"],
                template="""
You are a mental health professional analyzing text for signs of depression. 

Analyze the following conversation excerpt and determine if it contains content related to depression, mental health struggles, or emotional distress.

Look for indicators such as:
- Expressions of sadness, hopelessness, or despair
- Mentions of depression, anxiety, or mental health issues
- Feelings of worthlessness or emptiness
- Sleep or appetite changes
- Loss of interest or motivation
- Suicidal thoughts or self-harm mentions
- Seeking mental health help or therapy

Conversation text:
"{conversation_text}"

Respond with ONLY a JSON object in this exact format:
{{"is_depression_related": true/false, "confidence": 0.0-1.0, "key_indicators": ["indicator1", "indicator2"]}}

Do not include any explanation or additional text.
"""
            )

            # Create the LLM chain
            self.depression_chain = LLMChain(
                llm=self.llm,
                prompt=depression_prompt
            )

            print("Depression classifier LLM chain set up successfully")

        except Exception as e:
            print(f"Error setting up LLM: {e}")
            print("Please ensure you have set your OpenAI API key")

    def load_data(self):
        try:
            self.df = pd.read_csv(self.csv_file_path)
            print(f"Loaded {len(self.df)} sentences")

            if len(self.df.columns) == 1:
                self.df.columns = ['text']
                self.text_column = 'text'

            # NEW: force strings and strip, handle NaN
            self.df[self.text_column] = (
                self.df[self.text_column]
                .astype(str)
                .fillna("")
                .str.strip()
            )

            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False


    def create_embeddings(self, method='sentence_transformer'):
        """
        Create embeddings for the sentences

        Args:
            method (str): 'sentence_transformer' or 'tfidf'
        """
        print(f"Creating embeddings using {method}...")

        if method == 'sentence_transformer':
            # Prepare clean text list
            text_list = self.df[self.text_column].tolist()

            # Additional cleaning - ensure all items are strings and not empty
            clean_texts = []
            for text in text_list:
                if isinstance(text, str) and text.strip():
                    clean_texts.append(text.strip())
                else:
                    clean_texts.append("empty text")  # Replace problematic entries

            print(f"Processing {len(clean_texts)} clean text entries...")

            # Using sentence transformer for better semantic understanding
            model = SentenceTransformer('all-MiniLM-L6-v2')  # Lightweight model
            self.embeddings = model.encode(clean_texts, show_progress_bar=True)

        elif method == 'tfidf':
            # Alternative: TF-IDF vectors
            vectorizer = TfidfVectorizer(max_features=1000,
                                         stop_words='english',
                                         ngram_range=(1, 2))
            self.embeddings = vectorizer.fit_transform(self.df[self.text_column]).toarray()

        print(f"Created embeddings with shape: {self.embeddings.shape}")

    def find_optimal_clusters(self, min_k=350, max_k=400, step=5):
        """
        Find optimal number of clusters using elbow method and silhouette score
        """
        print("Finding optimal number of clusters...")

        k_range = range(min_k, max_k + 1, step)
        inertias = []
        silhouette_scores = []

        for k in k_range:
            print(f"Testing k={k}")
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(self.embeddings)

            inertias.append(kmeans.inertia_)
            sil_score = silhouette_score(self.embeddings, cluster_labels)
            silhouette_scores.append(sil_score)

        # Plot results
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

        ax1.plot(k_range, inertias, 'bo-')
        ax1.set_xlabel('Number of Clusters (k)')
        ax1.set_ylabel('Inertia')
        ax1.set_title('Elbow Method for Optimal k')
        ax1.grid(True)

        ax2.plot(k_range, silhouette_scores, 'ro-')
        ax2.set_xlabel('Number of Clusters (k)')
        ax2.set_ylabel('Silhouette Score')
        ax2.set_title('Silhouette Score vs Number of Clusters')
        ax2.grid(True)

        plt.tight_layout()
        plt.show()

        # Find best k based on silhouette score
        best_k = k_range[np.argmax(silhouette_scores)]
        print(f"Best k based on silhouette score: {best_k}")

        return k_range, inertias, silhouette_scores, best_k

    def cluster_conversations(self, n_clusters=378, map_out_path="./clustered_sentences.csv"):
        print(f"Clustering into {n_clusters} conversations...")
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.clusters = self.kmeans.fit_predict(self.embeddings)

        # Add cluster labels
        self.df['conversation_id'] = self.clusters
        print("Clustering completed!")

        # NEW: save [input, conv_id] map if requested
        if map_out_path:
            out_df = self.df[[self.text_column, 'conversation_id']].rename(
                columns={self.text_column: 'input', 'conversation_id': 'conv_id'}
            )
            out_df.to_csv(map_out_path, index=False, encoding='utf-8')
            print(f"Saved cluster map to {map_out_path}")

        self.analyze_clusters()
    def classify_single_conversation_llm(self, conversation_text: str, max_retries: int = 3) -> Dict:
        """
        Classify a single conversation using LLM

        Args:
            conversation_text (str): The conversation text to classify
            max_retries (int): Maximum number of retries for API calls

        Returns:
            Dict: Classification results
        """
        if not self.depression_chain:
            return {
                'is_depression_related': False,
                'confidence': 0.0,
                'key_indicators': [],
                'error': 'LLM chain not initialized'
            }

        # Truncate very long conversations to avoid token limits
        max_chars = 3000
        if len(conversation_text) > max_chars:
            conversation_text = conversation_text[:max_chars] + "..."

        for attempt in range(max_retries):
            try:
                # Call the LLM chain
                response = self.depression_chain.run(conversation_text=conversation_text)

                # Parse the JSON response
                try:
                    result = json.loads(response.strip())
                    return {
                        'is_depression_related': result.get('is_depression_related', False),
                        'confidence': result.get('confidence', 0.0),
                        'key_indicators': result.get('key_indicators', []),
                        'raw_response': response
                    }
                except json.JSONDecodeError:
                    # Fallback parsing if JSON is malformed
                    is_depression = 'true' in response.lower()
                    return {
                        'is_depression_related': is_depression,
                        'confidence': 0.5,
                        'key_indicators': [],
                        'raw_response': response
                    }

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                else:
                    return {
                        'is_depression_related': False,
                        'confidence': 0.0,
                        'key_indicators': [],
                        'error': str(e)
                    }

    def classify_all_conversations_depression(self, batch_size: int = 10):
        if 'conversation_id' not in self.df.columns:
            print("Please run clustering first!")
            return

        if not self.depression_chain:
            print("LLM chain not initialized. Skipping depression classification.")
            # still create a minimal conversation summary so downstream code works
            conversation_groups = self.df.groupby('conversation_id')
            results = []
            for conv_id, grp in conversation_groups:
                preview = " ".join([str(s) for s in grp[self.text_column].tolist()])[:200]
                results.append({
                    'conversation_id': conv_id,
                    'sentence_count': len(grp),
                    'is_depression_related': False,
                    'confidence': 0.0,
                    'key_indicators': [],
                    'conversation_preview': preview
                })
            self.conversation_results = pd.DataFrame(results)
            # add flag column back to df
            self.df['is_depression_related'] = False
            return

        print("Classifying conversations for depression using LLM...")

        conversation_groups = self.df.groupby('conversation_id')
        unique_conversations = list(conversation_groups.groups.keys())

        results = []
        total_conversations = len(unique_conversations)

        for idx, conv_id in enumerate(unique_conversations):
            if idx % batch_size == 0:
                print(f"Processing conversation {idx + 1}/{total_conversations}")

            # NEW: coerce to strings before join
            conv_sentences = [str(s) for s in conversation_groups.get_group(conv_id)[self.text_column].tolist()]
            conversation_text = ' '.join(conv_sentences).strip()

            classification_result = self.classify_single_conversation_llm(conversation_text)

            results.append({
                'conversation_id': conv_id,
                'sentence_count': len(conv_sentences),
                'is_depression_related': classification_result.get('is_depression_related', False),
                'confidence': classification_result.get('confidence', 0.0),
                'key_indicators': classification_result.get('key_indicators', []),
                'conversation_preview': conversation_text[:200] + "..." if len(
                    conversation_text) > 200 else conversation_text
            })

            time.sleep(0.1)

        self.conversation_results = pd.DataFrame(results)

        depression_mapping = dict(zip(
            self.conversation_results['conversation_id'],
            self.conversation_results['is_depression_related']
        ))
        self.df['is_depression_related'] = self.df['conversation_id'].map(depression_mapping)

        print("Depression classification completed!")
        self.analyze_depression_results()

    def analyze_depression_results(self):
        """Analyze depression classification results"""
        if not hasattr(self, 'conversation_results'):
            print("No classification results found!")
            return

        print("\n=== Depression Classification Analysis ===")

        depression_count = self.conversation_results['is_depression_related'].sum()
        total_count = len(self.conversation_results)

        print(f"Total conversations: {total_count}")
        print(f"Depression-related conversations: {depression_count}")
        print(f"Non-depression conversations: {total_count - depression_count}")
        print(f"Depression rate: {depression_count / total_count * 100:.1f}%")

        # Show confidence distribution
        plt.figure(figsize=(12, 5))

        plt.subplot(1, 2, 1)
        depression_convs = self.conversation_results[self.conversation_results['is_depression_related']]
        non_depression_convs = self.conversation_results[~self.conversation_results['is_depression_related']]

        plt.hist([depression_convs['confidence'], non_depression_convs['confidence']],
                 bins=20, alpha=0.7, label=['Depression', 'Non-depression'])
        plt.xlabel('Confidence Score')
        plt.ylabel('Number of Conversations')
        plt.title('Classification Confidence Distribution')
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        labels = ['Depression-related', 'Non-depression']
        sizes = [depression_count, total_count - depression_count]
        colors = ['#ff6b6b', '#4ecdc4']

        plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        plt.title('Conversation Classification Distribution')

        plt.tight_layout()
        plt.show()

    def show_sample_depression_conversations(self, n_samples=3):
        """Show sample depression-related conversations"""
        if not hasattr(self, 'conversation_results'):
            print("No classification results found!")
            return

        depression_convs = self.conversation_results[
            self.conversation_results['is_depression_related']
        ].head(n_samples)

        print(f"\n=== Sample Depression-Related Conversations ===")

        for _, conv in depression_convs.iterrows():
            conv_data = self.df[self.df['conversation_id'] == conv['conversation_id']]

            print(f"\n--- Conversation {conv['conversation_id']} ---")
            print(f"Confidence: {conv['confidence']:.2f}")
            print(f"Key indicators: {conv['key_indicators']}")
            print(f"Sentences ({len(conv_data)}):")

            for idx, (_, row) in enumerate(conv_data.head(5).iterrows()):
                print(f"  {idx + 1}. {row[self.text_column]}")

            if len(conv_data) > 5:
                print(f"  ... and {len(conv_data) - 5} more sentences")

    def analyze_clusters(self):
        """Analyze the clustering results"""
        print("\n=== Clustering Analysis ===")

        # Basic statistics
        cluster_counts = self.df['conversation_id'].value_counts().sort_index()
        print(f"Number of clusters: {len(cluster_counts)}")
        print(f"Average sentences per conversation: {cluster_counts.mean():.2f}")
        print(f"Std dev sentences per conversation: {cluster_counts.std():.2f}")
        print(f"Min sentences in a conversation: {cluster_counts.min()}")
        print(f"Max sentences in a conversation: {cluster_counts.max()}")

        # Show distribution
        plt.figure(figsize=(12, 5))

        plt.subplot(1, 2, 1)
        plt.hist(cluster_counts, bins=30, edgecolor='black')
        plt.xlabel('Sentences per Conversation')
        plt.ylabel('Frequency')
        plt.title('Distribution of Conversation Lengths')
        plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        plt.boxplot(cluster_counts)
        plt.ylabel('Sentences per Conversation')
        plt.title('Conversation Length Distribution')
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def save_results(self, output_file='clustered_conversations_with_depression.csv'):
        """Save the clustered and classified results to CSV"""
        self.df.to_csv(output_file, index=False)
        print(f"Results saved to {output_file}")

        # Save conversation-level results
        if hasattr(self, 'conversation_results'):
            conv_file = output_file.replace('.csv', '_conversation_summary.csv')
            self.conversation_results.to_csv(conv_file, index=False)
            print(f"Conversation summary saved to {conv_file}")


# Usage example
def main():
    # Initialize clusterer (will automatically load API key from .env file)
    clusterer = ConversationClusterer('./sentences.csv')

    # Load data
    if not clusterer.load_data():
        return

    # Create embeddings
    clusterer.create_embeddings(method='sentence_transformer')

    # Cluster into conversations
    clusterer.cluster_conversations(n_clusters=378)

    # Classify conversations for depression
    clusterer.classify_all_conversations_depression(batch_size=10)

    # Show sample results
    clusterer.show_sample_depression_conversations(n_samples=3)

    # Save results
    clusterer.save_results('clustered_conversations_with_depression.csv')


if __name__ == "__main__":
    main()