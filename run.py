from fraas import create_app


app = create_app()


if __name__ == "__main__":
    # For development. In production, use a proper WSGI server like gunicorn or uWSGI.
    app.run(host="0.0.0.0", port=5000, debug=True)


