#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 16.raptor_recursive_document_tree_optimization.py
"""
import os
from typing import Optional

import dotenv
import numpy as np
import pandas as pd
import umap
import weaviate
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_weaviate import WeaviateVectorStore
from sklearn.mixture import GaussianMixture
from weaviate.auth import AuthApiKey

# Load environment variables
dotenv.load_dotenv()

# 1. Define random seed, embedding model, language model, and vector database
RANDOM_SEED = 224
embd = HuggingFaceEmbeddings(
    model_name="thenlper/gte-small",
    cache_folder="./embeddings/",
    encode_kwargs={"normalize_embeddings": True},
)
model = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="RaptorRAG",
    text_key="text",
    embedding=embd,
)


def global_cluster_embeddings(
        embeddings: np.ndarray,
        dim: int,
        n_neighbors: Optional[int] = None,
        metric: str = "cosine",
) -> np.ndarray:
    """
    Perform global dimensionality reduction on the input embeddings using UMAP.

    :param embeddings: The embedding vectors to reduce.
    :param dim: The target number of dimensions.
    :param n_neighbors: Number of neighbors for UMAP; defaults to sqrt(number of embeddings) if None.
    :param metric: Distance metric to use for UMAP; default is cosine similarity.
    :return: A numpy array of embeddings reduced to the specified dimension.
    """
    if n_neighbors is None:
        n_neighbors = int((len(embeddings) - 1) ** 0.5)
    return umap.UMAP(n_neighbors=n_neighbors, n_components=dim, metric=metric).fit_transform(embeddings)


def local_cluster_embeddings(
        embeddings: np.ndarray,
        dim: int,
        n_neighbors: int = 10,
        metric: str = "cosine",
) -> np.ndarray:
    """
    Perform local dimensionality reduction on embeddings using UMAP, typically after global clustering.

    :param embeddings: The embedding vectors to reduce.
    :param dim: The target number of dimensions.
    :param n_neighbors: Number of neighbors for UMAP.
    :param metric: Distance metric to use for UMAP; default is cosine similarity.
    :return: A numpy array of embeddings reduced to the specified dimension.
    """
    return umap.UMAP(n_neighbors=n_neighbors, n_components=dim, metric=metric).fit_transform(embeddings)


def get_optimal_clusters(
        embeddings: np.ndarray,
        max_clusters: int = 50,
        random_state: int = RANDOM_SEED,
) -> int:
    """
    Determine the optimal number of clusters using Gaussian Mixture Model (GMM) and Bayesian Information Criterion (BIC).

    :param embeddings: The embedding vectors to cluster.
    :param max_clusters: Maximum number of clusters to consider.
    :param random_state: Random seed for reproducibility.
    :return: The optimal number of clusters.
    """
    max_clusters = min(max_clusters, len(embeddings))
    n_clusters = np.arange(1, max_clusters)
    bics = []
    for n in n_clusters:
        gm = GaussianMixture(n_components=n, random_state=random_state)
        gm.fit(embeddings)
        bics.append(gm.bic(embeddings))
    return n_clusters[np.argmin(bics)]


def gmm_cluster(
        embeddings: np.ndarray,
        threshold: float,
        random_state: int = 0
) -> tuple[list, int]:
    """
    Cluster embeddings using a Gaussian Mixture Model with a probability threshold.

    :param embeddings: The embedding vectors to cluster (after dimensionality reduction).
    :param threshold: Probability threshold for cluster assignment.
    :param random_state: Random seed for reproducibility.
    :return: A tuple containing the list of cluster labels per sample and the number of clusters.
    """
    n_clusters = get_optimal_clusters(embeddings)
    gm = GaussianMixture(n_components=n_clusters, random_state=random_state)
    gm.fit(embeddings)
    probs = gm.predict_proba(embeddings)
    labels = [np.where(prob > threshold)[0] for prob in probs]
    return labels, n_clusters


def perform_clustering(
        embeddings: np.ndarray,
        dim: int,
        threshold: float
) -> list[np.ndarray]:
    """
    Perform hierarchical clustering on embeddings: global reduction & clustering, then local clustering within each global cluster.

    :param embeddings: Array of embedding vectors.
    :param dim: Target dimension for reduction.
    :param threshold: Probability threshold for GMM clustering.
    :return: List of arrays, each array containing cluster IDs for each embedding.
    """
    if len(embeddings) <= dim + 1:
        return [np.array([0]) for _ in range(len(embeddings))]

    reduced_global = global_cluster_embeddings(embeddings, dim)
    global_labels, n_global = gmm_cluster(reduced_global, threshold)

    all_local = [np.array([]) for _ in range(len(embeddings))]
    total_clusters = 0

    for i in range(n_global):
        mask = np.array([i in lbl for lbl in global_labels])
        cluster_embs = embeddings[mask]
        if len(cluster_embs) == 0:
            continue
        if len(cluster_embs) <= dim + 1:
            local_labels = [np.array([0]) for _ in cluster_embs]
            n_local = 1
        else:
            reduced_local = local_cluster_embeddings(cluster_embs, dim)
            local_labels, n_local = gmm_cluster(reduced_local, threshold)
        for j in range(n_local):
            submask = np.array([j in lbl for lbl in local_labels])
            indices = np.where(mask)[0][submask]
            for idx in indices:
                all_local[idx] = np.append(all_local[idx], j + total_clusters)
        total_clusters += n_local

    return all_local


def embed(texts: list[str]) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    :param texts: List of text strings.
    :return: Array of embedding vectors.
    """
    return np.array(embd.embed_documents(texts))


def embed_cluster_texts(texts: list[str]) -> pd.DataFrame:
    """
    Embed and cluster texts, returning a DataFrame with text, embedding, and cluster labels.

    :param texts: List of text strings.
    :return: DataFrame with columns ['text', 'embd', 'cluster'].
    """
    embs = embed(texts)
    clusters = perform_clustering(embs, dim=10, threshold=0.1)
    df = pd.DataFrame({"text": texts, "embd": list(embs), "cluster": clusters})
    return df


def fmt_txt(df: pd.DataFrame) -> str:
    """
    Format DataFrame texts into a single string for summarization.

    :param df: DataFrame with 'text' column.
    :return: Joined string of texts.
    """
    return "\n---\n".join(df["text"].tolist())


def embed_cluster_summarize_texts(
        texts: list[str],
        level: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Embed, cluster, and summarize texts at a given level.

    :param texts: List of text strings.
    :param level: Current processing level.
    :return: Tuple of (cluster DataFrame, summary DataFrame).
    """
    df_clusters = embed_cluster_texts(texts)
    expanded = []
    for _, row in df_clusters.iterrows():
        for c in row["cluster"]:
            expanded.append({"text": row["text"], "embd": row["embd"], "cluster": c})
    exp_df = pd.DataFrame(expanded)
    unique_clusters = exp_df["cluster"].unique()

    summary_template = """Here is a subset of documentation. Please provide a detailed summary:

{context}
"""
    prompt = ChatPromptTemplate.from_template(summary_template)
    chain = prompt | model | StrOutputParser()

    summaries = []
    for c in unique_clusters:
        sub_df = exp_df[exp_df["cluster"] == c]
        context = fmt_txt(sub_df)
        summaries.append(chain.invoke({"context": context}))

    df_summary = pd.DataFrame({
        "summaries": summaries,
        "level": [level] * len(summaries),
        "cluster": list(unique_clusters),
    })

    return df_clusters, df_summary


def recursive_embed_cluster_summarize(
        texts: list[str],
        level: int = 1,
        n_levels: int = 3
) -> dict[int, tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Recursively embed, cluster, and summarize texts up to a specified depth.

    :param texts: List of text strings.
    :param level: Current recursion level (starts at 1).
    :param n_levels: Maximum recursion depth.
    :return: Dictionary mapping level to (cluster DataFrame, summary DataFrame).
    """
    results: dict[int, tuple[pd.DataFrame, pd.DataFrame]] = {}
    df_clust, df_sum = embed_cluster_summarize_texts(texts, level)
    results[level] = (df_clust, df_sum)

    if level < n_levels and df_sum["cluster"].nunique() > 1:
        next_texts = df_sum["summaries"].tolist()
        next_results = recursive_embed_cluster_summarize(next_texts, level + 1, n_levels)
        results.update(next_results)

    return results


# 2. Define document loaders and text splitter (for Chinese and English contexts)
loaders = [
    UnstructuredFileLoader("./ecommerce_product_data.txt"),
    UnstructuredFileLoader("./project_api_docs.md"),
]
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=0,
    separators=["\n\n", "\n", "。|！|？", r"\.\s|\!\s|\?\s", "；|;\s", "，|,\s", " ", ""],
    is_separator_regex=True,
)

# 3. Split and load texts in a loop
docs = []
for loader in loaders:
    docs.extend(loader.load_and_split(text_splitter))

# 4. Build document tree up to 3 levels
leaf_texts = [doc.page_content for doc in docs]
results = recursive_embed_cluster_summarize(leaf_texts, level=1, n_levels=3)

# 5. Iterate over results, extract summaries at each level, and add them to all_texts
all_texts = leaf_texts.copy()
for lvl in sorted(results.keys()):
    all_texts.extend(results[lvl][1]["summaries"].tolist())

# 6. Add all_texts to the vector database
db.add_texts(all_texts)

# 7. Perform similarity search (collapsed tree)
retriever = db.as_retriever(search_type="mmr")
search_docs = retriever.invoke("How long did it take humanity in 'The Wandering Earth' to reach the new star system?")

print(search_docs)
print(f"Number of results: {len(search_docs)}")
