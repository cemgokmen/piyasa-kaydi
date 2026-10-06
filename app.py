"""
Siteyi başlatır:  python app.py   (ya da: python -m piyasa site)
"""

from piyasa.web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
