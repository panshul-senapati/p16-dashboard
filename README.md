# 📊 GitHub Analytics Dashboard for pandas-dev/pandas

This project is a Streamlit-based interactive dashboard that visualizes real-time GitHub repository data (stars, forks, pull requests, downloads, etc.) for the [`pandas-dev/pandas`](https://github.com/pandas-dev/pandas) repository using GitHub's GraphQL API. It provides data analysts, developers, and open-source contributors with intuitive insights into project popularity and contributions over time.

---

## 🔧 Features

- ✅ Fetches real-time data from GitHub using GraphQL API
- 📈 Visualizes stars, forks, pull requests, and download trends
- 🗓️ Custom date-range selection for dynamic filtering
- ⚡ Efficient data caching using `st.cache_data` for faster reloads
- 🎨 Responsive and interactive UI built with Streamlit and Plotly

---

## 📂 Project Structure

p16_dashboard/
├── app.py # Main Streamlit app
├── graphql.py # GraphQL utility functions for GitHub API
├── data/ # Contains CSVs for stars, forks, PRs, downloads
├── assets/ # (Optional) Images, logos, or static files
├── requirements.txt # Python dependencies
└── README.md # Project documentation


---

## 🚀 How to Run

### 1. Clone the Repository

```bash
git clone https://github.com/panshul-senapati/p16-dashboard.git
cd p16-dashboard
2. Set up Python Environment
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
3. Install Dependencies
pip install -r requirements.txt
4. Add GitHub Personal Access Token
Create a .env file and add your GitHub token:

GITHUB_TOKEN=your_personal_access_token
Tip: Create a token at https://github.com/settings/tokens with repo and read:packages scopes.
5. Run the App
streamlit run app.py
📊 Sample Visualizations

⭐ Stars and forks over time (line charts)
🔀 Pull requests by month (bar charts)
📥 Monthly download counts (bar + line combo)
📅 Date range selector for dynamic analysis
🛠️ Built With

Python
Streamlit
Plotly
Pandas
GitHub GraphQL API
🧰 Developer Tools

Visual Studio Code
Git & GitHub
virtualenv
Streamlit CLI
API testing tools (e.g., Postman)
