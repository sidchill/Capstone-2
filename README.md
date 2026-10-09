##Architecture Design
User Query
The user submits a question through the terminal after running the CLI entry point file.
|
v

Manager Agent
The Manager Agent classifies the question as qualitative, quantitative, or both.
|
v

Qualitative Path
The Qualitative Agent searches the ChromaDB index in data/chroma/ for relevant information from data/documents/documents.txt. Gemini then generates a response based on the retrieved document content.
Quantitative Path
The Quantitative Agent uses data/database.sqlite as the source for numerical information. Gemini converts the user’s question into the SQL language, and then it executes the query using the database.
|
v

Validation Layer
The Validation Layer checks that the response is supported by the documents and/or database. It also notes execution errors, unsupported claims, and numerical mistakes.
|
v

Tokenomics Logger
The Tokenomics Logger records token + cost information per query.
|
v

Response to User
The validated response is returned to the user through the command-line interface.
##SETUP AND PROCESS
To set up the environment you must run:
python -m venv venv
source venv/bin/activate

You must install these processes:
pip install google-genai
pip install chromadb
pip install sentence-transformers
pip install python-dotenv

pip freeze > requirements.txt

Set up your .env file to have:
GEMINI_API_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_INPUT_COST_PER_1M=0.30
GEMINI_OUTPUT_COST_PER_1M=2.50
GEMINI_MANAGER_MODEL=gemini-3.8-flash

To use this code you can just clone the repository using git clone <url> then simply cd into the file and write code .

After this you must run python ingest.py, and then you can run python main.py and the program will be up and running

##TRUST BUT VERIFY
Query 1: "What is our company's security policy?"

What Gemini returned: 
These were the costs for my query:

[TOKENOMICS] Agent: manager-classifier | Input: 97 | Output: 2 | Cost: $0.000034

[TOKENOMICS] Agent: qualitative | Input: 723 | Output: 358 | Cost: $0.001112

The manager agent routed the query to the correct set of guidelines in qualitative.py.

The company's security policy encompasses the following guidelines:

* **Protection & Authentication:** The company protects business, customer, and employee information, as well as credentials, through access controls, secure practices, and employee awareness [Source 1]. Employees must use multifactor authentication where available, protect passwords and tokens, and never share credentials [Source 1].
* **Access Control:** System and data access is granted based on job responsibilities and the principle of least privilege, and confidential information may only be accessed for authorized business purposes [Source 1, Source 2].
* **Device & Software Security:** Company devices must utilize approved security controls, current software updates, screen locks, and endpoint protection [Source 1, Source 2]. Employees must not install unauthorized software or transfer confidential data to personal accounts, unapproved applications, or removable media [Source 2].
* **Incident Reporting:** Any suspected security incidents (phishing, malware, unauthorized access, lost devices, or data disclosures) must be reported immediately to the security team [Source 2]. Employees must preserve evidence and not investigate or delete suspicious messages unless directed by security personnel [Source 2, Source 3].
* **Data Storage & Transmission:** Confidential information must be handled using approved systems and kept out of public messages, unsecured documents, or unapproved collaboration tools [Source 3, Source 4].
* **Compliance, Exceptions & Violations:** Employees must complete mandatory security awareness training and adhere to privacy and data-retention rules [Source 3, Source 5]. Policy exceptions require documented business justification and approval from management or security owners, while violations may result in loss of access, additional training, investigation, or other corrective actions [Source 3, Source 5].

What the validation layer flagged, if anything:
The validation layer did not flag anything for this query

What I accepted, what you changed, and why:
I reduced the document chunk size, and subsequently split the source material into separate sections that exist within the documents in folder.  When I had initially ran ingest.py I noticed that it was only taking in one large chunk, which eliminates the possibility of mixed information.  By splitting up the documents the model can avoid viewing policies that are unrelated but may find their way into the query, thus providing a more optimal result.  Essentially I was improving the precision of the retrieval process, by implementing this change.

One case where Gemini produced an output you did not immediately trust — and how you resolved it:
The initial query involved what I considered to be information that was not relevant to the security policy I was asking for, which led to me making the change I listed above.  Additionally, on my final query I made sure to read through the output, and cross reference the content with the corresponding document company_security_policy.txt

Query 2: "Show me monthly revenue trends"

What Gemini returned:
These were the costs for my query:

[TOKENOMICS] Agent: manager-classifier | Input: 93 | Output: 1 | Cost: $0.000030

[TOKENOMICS] Agent: quantitative | Input: 281 | Output: 162 | Cost: $0.000489

The manager agent once again correctly routed me to the correct place, which was quantitative this time

Based on the data, the monthly revenue trends for 2026 are as follows:

* **January:** $368,000.0 (highest revenue)
* **February:** $265,000.0
* **March:** $168,000.0 (lowest revenue)
* **April:** $295,000.0
* **May:** $73,000.0

Revenue fluctuated over this five-month period, decreasing from January to March, increasing in April, and dropping to the lowest recorded amount in May.
SQL used: SELECT strftime('%Y-%m', date) AS month, SUM(revenue) AS total_revenue FROM sales GROUP BY month ORDER BY month;

What the validation layer flagged, if anything: 
When I initially entered this query, it was flagged with a Query execution failed: 503 UNAVAILABLE error.  This was mitigated by simply waiting for an alloted period of time and retrying the prompt.

What I accepted, what I changed, and why:
The first output was rejected, due to the fact that an error message was relayed.  I reran the query and confirmed that it was returning monthly totals as expected and received no validation warning.  I experimented with the temperature, but ultimately due to this being a quantitative query, I decided to go with a temperature of 0 for the sql function.  This is because a deterministic nature is expected for quantitative queries as the answer should not vary in the same way a qualitative result might.

One case where Gemini  produced an output you did not immediately trust — and how you resolved it:
I did not immediately trust the output.  I opened my database.sql and ran the following command:
sqlite3 -header -column data/database.sqlite "SELECT strftime('%Y-%m', date) AS month, SUM(revenue) AS total_revenue FROM sales GROUP BY month ORDER BY month;"

My database was modified, so I had to run a series of commands to fix that which ended up in me having to sqlite files with one being a backup.

This allowed me to cross reference the output was showing from the query I sent into Gemini, and it matched succesfully.  THe only issue is that Gemini labeled March as the lowest revenue, when it was actually May.  It likely did not compare May as it would have thought the month was ongoing which was an assumption I did not provide to the model itself.  This output does not require any resolution besides manual change, or one could use a complex multi agent RAG process to combine this with an employee salary document that indicates all months should be looked at without considering that the final month is ongoing.

Query 3: ""How does our employee satisfaction compare to industry standards and what policies might impact this?"
**Note that the extra quotation mark was actually included in the original prompt on accident

What Gemini returned:
These were the costs for my query:

[TOKENOMICS] Agent: manager-classifier | Input: 105 | Output: 1 | Cost: $0.000034

[TOKENOMICS] Agent: qualitative | Input: 696 | Output: 128 | Cost: $0.000529

[TOKENOMICS] Agent: quantitative | Input: 281 | Output: 165 | Cost: $0.000497

For the third time, the manager agent routed me to the correct route, which was a path that utilized both the qualitative and quantitative guidelines.  It separated the aspects as provided below:

[Qualitative]
The current project database does not contain an external industry benchmark, so the system should not claim that employee satisfaction is above or below industry standards unless a separate benchmark dataset is provided [Source 1, Source 5]. 

Employee satisfaction may be influenced by workload, manager effectiveness, career development, recognition, compensation, flexibility, training, communication, and psychological safety [Source 3, Source 4]. Potential policy responses to address lower scores include manager check-ins, workload reviews, professional development plans, recognition programs, clearer escalation channels, improved onboarding, and targeted retention outreach [Source 1, Source 3, Source 4].

[Quantitative]
Based on the provided data, employee satisfaction scores vary by department as follows:

* **Consulting:** 4.15 (Average tenure: 2.75 years)
* **Tax:** 4.0 (Average tenure: 4.5 years)
* **Audit:** 3.8 (Average tenure: 4.5 years)
* **Operations:** 3.7 (Average tenure: 4.25 years)

The results do not contain data regarding industry standards or specific company policies, so a comparison to industry standards and the identification of impacting policies cannot be provided from the given data.
SQL used: SELECT department, AVG(satisfaction_score) AS avg_employee_satisfaction, AVG(tenure_years) AS avg_tenure FROM employees GROUP BY department

What the validation layer flagged, if anything:
The validation layer did not flag anything during this query.

What I accepted, what I changed, and why:
I accepted the department averages after reviewing the generated SQL and confirmed that that the employees table contains department, satisfaction scores, and tenure data.  This query required no changes as the output was completely what I expected.

One case where Gemini  produced an output you did not immediately trust — and how you resolved it:
I did not immediately trust the quantitative aspect, as it was not obviously sourced from my documents folder.  So, I ran another SQL query as before to ensure that the data that Gemini was showing came directly from the data from my database.sqlite folder.  