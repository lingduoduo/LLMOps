#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : qa_transformer_example.py
"""
import dotenv
from langchain_community.document_transformers import DoctranQATransformer
from langchain_core.documents import Document

dotenv.load_dotenv()

# 1. Build the list of documents
page_content = """Confidential Document - For Internal Use Only
Date: July 1, 2023
Subject: Updates and Discussions on Various Topics

Dear Team,

I hope this email finds you well. In this document, I would like to provide you with some important updates and discuss various topics requiring our attention. Please treat the information contained herein as highly confidential.

Security and Privacy Measures
As part of our ongoing commitment to ensuring customer data security and privacy, we have implemented robust measures across all systems. We want to commend John Doe (email: john.doe@example.com) from the IT department for his diligent work in enhancing our cybersecurity. Moving forward, we remind everyone to strictly adhere to our data protection policies and guidelines. Additionally, if you identify any potential security risks or incidents, please report them immediately to our dedicated team at security@example.com.

Human Resources Updates and Employee Benefits
Recently, we welcomed several new team members who have made significant contributions to their respective departments. I would like to recognize Jane Smith (SSN: 049-45-5928) for her outstanding performance in customer service. Jane has received positive feedback from customers. Additionally, please remember that the open enrollment period for our employee benefits program is approaching. If you have any questions or need assistance, please contact our HR representative Michael Johnson (phone: 418-492-3850, email: michael.johnson@example.com).

Marketing Initiatives and Events
Our marketing team has been actively developing new strategies to raise brand awareness and drive customer engagement. We want to thank Sarah Thompson (phone: 415-555-1234) for her exceptional efforts in managing our social media platforms. Sarah successfully increased our follower base by 20% over the past month. Additionally, please note the upcoming product launch event on July 15. We encourage all team members to attend and support this important company milestone.

R&D Projects
In our pursuit of innovation, our R&D department has been working tirelessly on various projects. I would like to commend David Rodriguez (email: david.rodriguez@example.com) for his outstanding work as project lead. David has made significant contributions to the development of our cutting-edge technologies. Furthermore, we encourage everyone to share their ideas and suggestions at the regular R&D brainstorming meeting on July 10 to explore potential new projects.

Please treat the information in this document as highly confidential and ensure it is not shared with unauthorized personnel. If you have any questions or concerns regarding the topics discussed, feel free to contact me directly.

Thank you for your attention, and let us continue working together to achieve our goals.

Sincerely,
Jason Fan
Co-founder & CEO
Psychic
jason@psychic.dev"""

documents = [Document(page_content=page_content)]

# 2. Build the Q&A transformer and transform
doc_qa = DoctranQATransformer(openai_api_model="gpt-3.5-turbo-16k")
transformed_docs = doc_qa.transform_documents(documents)

# 3. Output the Q&A data
for qa in transformed_docs[0].metadata.get("questions_and_answers", []):
    print("Q&A data:", qa)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : text_translator_example.py
"""
import dotenv
from langchain_community.document_transformers import DoctranTextTranslator
from langchain_core.documents import Document

dotenv.load_dotenv()

# 1. Construct the list of documents
page_content = """机密文件 - 仅供内部使用
日期：2023年7月1日
主题：各种话题的更新和讨论
亲爱的团队，
希望这封邮件能找到你们一切安好。在这份文件中，我想向你们提供一些重要的更新，并讨论需要我们关注的各种话题。请将此处包含的信息视为高度机密。

安全和隐私措施
作为我们不断致力于确保客户数据安全和隐私的一部分，我们已在所有系统中实施了强有力的措施。我们要赞扬IT部门的John Doe（电子邮件：john.doe@example.com）在增强我们网络安全方面的勤奋工作。未来，我们提醒每个人严格遵守我们的数据保护政策和准则。此外，如果您发现任何潜在的安全风险或事件，请立即向我们专门的团队报告，联系邮箱为security@example.com。

人力资源更新和员工福利
最近，我们迎来了几位为各自部门做出重大贡献的新团队成员。我要表扬Jane Smith（社保号：049-45-5928）在客户服务方面的出色表现。Jane一直受到客户的积极反馈。此外，请记住我们的员工福利计划的开放报名期即将到来。如果您有任何问题或需要帮助，请联系我们的人力资源代表Michael Johnson（电话：418-492-3850，电子邮件：michael.johnson@example.com）。

营销倡议和活动
我们的营销团队一直在积极制定新策略，以提高品牌知名度并推动客户参与。我们要感谢Sarah Thompson（电话：415-555-1234）在管理我们的社交媒体平台方面的杰出努力。Sarah在过去一个月内成功将我们的关注者基数增加了20%。此外，请记住7月15日即将举行的产品发布活动。我们鼓励所有团队成员参加并支持我们公司的这一重要里程碑。

研发项目
在追求创新的过程中，我们的研发部门一直在为各种项目不懈努力。我要赞扬David Rodriguez（电子邮件：david.rodriguez@example.com）在项目负责人角色中的杰出工作。David对我们尖端技术的发展做出了重要贡献。此外，我们希望每个人在7月10日定期举行的研发头脑风暴会议上分享他们的想法和建议，以开展潜在的新项目。

请将此文档中的信息视为最机密，并确保不与未经授权的人员分享。如果您对讨论的话题有任何疑问或顾虑，请随时直接联系我。

感谢您的关注，让我们继续共同努力实现我们的目标。

此致，
Jason Fan
联合创始人兼首席执行官
Psychic
jason@psychic.dev"""

documents = [Document(page_content=page_content)]

# 2. Initialize the text translator and translate the documents
translator = DoctranTextTranslator(openai_api_model="gpt-3.5-turbo-16k")
translated_docs = translator.transform_documents(documents)

# 3. Print the translated content
print(translated_docs[0].page_content)
