#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
from uuid import uuid1

import dotenv
import pandas as pd
from arize.experimental.datasets import ArizeDatasetsClient
from arize.experimental.datasets.utils.constants import GENERATIVE

dotenv.load_dotenv()

SPACE_ID = os.getenv("ARIZE_SPACE_ID")
API_KEY = os.getenv("ARIZE_API_KEY")

# os.environ['NO_PROXY'] = "otlp.arize.com" or "flight.arize.com"

df = pd.read_csv("/Users/linghuang/Git/LLMOps/study-template/arize/data.csv")
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

arize_client = ArizeDatasetsClient(api_key=API_KEY)
# Create a dataset from a DataFrame add your own data here
dataset_name = "docs-qa-new-" + str(uuid1())[:5]
dataset_id = arize_client.create_dataset(
    space_id=SPACE_ID,
    dataset_name=dataset_name,
    dataset_type=GENERATIVE,
    data=df,
)

dataset = arize_client.get_dataset(space_id=SPACE_ID, dataset_id=dataset_id)
print(dataset.head())
