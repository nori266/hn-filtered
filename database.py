import sqlite3
from typing import Dict

class ArticleDatabase:
    def __init__(self, db_name='articles.db'):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        """Create the articles table if it doesn't exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source TEXT,
                date TEXT,
                matches TEXT
            )
        ''')
        self.conn.commit()

    def save_article(self, article: Dict):
        """Save a processed article to the database."""
        try:
            matches_str = ', '.join([match['question'] for match in article.get('matches', [])])
            self.cursor.execute('''
                INSERT INTO articles (title, url, source, date, matches)
                VALUES (?, ?, ?, ?, ?)
            ''', (article['title'], article['url'], article['source'], article.get('date', ''), matches_str))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Article with this URL already exists
            pass

    def get_all_articles(self):
        """Retrieve all saved articles."""
        self.cursor.execute('SELECT title, url, source, date, matches FROM articles ORDER BY date DESC')
        return self.cursor.fetchall()

    def __del__(self):
        self.conn.close()
