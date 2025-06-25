## CablePro Deployment Guide for Render (Free Tier)

This guide covers deploying the Flask application from a GitHub repository to Render, including the workaround for initializing the database on the free tier.

### Phase 1: Local Project Preparation

Before deploying, ensure your project is correctly configured locally.

1.  **Prepare `app.py` for Setup:**
    *   Ensure your `app.py` contains the **temporary one-time setup function**. This function creates a secret URL that you will visit once to create your database tables. It should be placed **inside** the `create_app()` function, just before the `return app` line.
    ```python
    # Inside create_app() function...

    # ====================================================================
    # ONE-TIME SETUP ENDPOINT FOR RENDER (FREE TIER)
    # ====================================================================
    @app.route('/setup-the-database/a-very-secret-string-for-setup-123') # <-- CHOOSE YOUR OWN!
    def one_time_setup():
        # ... (full function code)
    
    return app
    ```

2.  **Create `requirements.txt`:**
    *   This file tells Render which Python packages to install. It must be in the root directory of your project (the same folder as `app.py`).
    *   Run these commands in your project's terminal:
        ```bash
        # Install the production server and database driver
        pip install gunicorn psycopg2-binary
        
        # Create/update the requirements file
        pip freeze > requirements.txt
        ```

3.  **Push to GitHub:**
    *   Commit all your files, including the updated `app.py` and the new `requirements.txt`, to your GitHub repository.
        ```bash
        git add .
        git commit -m "Prepare for initial Render deployment"
        git push
        ```

---

### Phase 2: Create Services on Render

You will create two services: a database and a web service that runs your code.

1.  **Create the PostgreSQL Database:**
    *   On the Render Dashboard, click **New +** > **PostgreSQL**.
    *   Give it a unique **Name** (e.g., `cablepro-db`).
    *   Select a **Region**.
    *   Click **Create Database**.
    *   Wait for it to become available.

2.  **Create the Web Service:**
    *   On the Dashboard, click **New +** > **Web Service**.
    *   Connect your GitHub account and select your `CablePro` repository.
    *   Fill in the settings:
        *   **Name:** A unique name (e.g., `cable-pro-app`).
        *   **Region:** Use the **same region** as your database.
        *   **Branch:** `main` (or your primary branch).
        *   **Build Command:** `pip install -r requirements.txt`
        *   **Start Command:** `python -m gunicorn "app:create_app()"`

    *   Scroll down to **Environment Variables**. This is critical.
        *   Click **Add Environment Variable** for each of the following:
            *   **Key:** `DATABASE_URL`
                *   **Value:** Click the "From existing service" button (or database icon) to the right and select your `cablepro-db` database. Render will fill in the correct Internal URL.
            *   **Key:** `SECRET_KEY`
                *   **Value:** Create a long, random string for security (e.g., use an online password generator).
            *   **Key:** `PYTHON_VERSION`
                *   **Value:** `3.12.3` (or the version you are using).

    *   Click **Create Web Service**. Render will now start building and deploying your application.

---

### Phase 3: The One-Time Database Setup

Once your deployment is "Live", your app is running but the database is empty.

1.  **Wait for Deployment:** Wait for the deployment status on Render to show **"Live"**.
2.  **Construct the Setup URL:**
    *   Get your app's main URL from the top of its Render page (e.g., `https://cable-pro-app.onrender.com`).
    *   Append the secret path you created in `app.py`.
    *   The final URL will be: `https://cable-pro-app.onrender.com/setup-the-database/a-very-secret-string-for-setup-123`
3.  **Visit the URL:** Paste the full setup URL into your browser and press Enter.
4.  **Confirm Success:** The page should display a message like `SUCCESS: Database tables created and admin user added.`
5.  **Test Login:** Go to your main site (`https://cable-pro-app.onrender.com`) and log in with the default credentials (`admin@cablepro.com`, password: `admin`) to confirm it works.

---

### Phase 4: Secure the Application (CRITICAL)

Now that the database is initialized, you must remove the temporary setup URL.

1.  **Remove the Code:**
    *   On your local computer, open `app.py` and **delete the entire `one_time_setup` function**.
    *   Save the file.
2.  **Push the Final Version to GitHub:**
    ```bash
    git add app.py
    git commit -m "Remove temporary setup endpoint for security"
    git push
    ```
3.  **Final Redeploy:**
    *   Render will see the new commit and automatically start a final deployment.
    *   Once this is "Live", your application is fully deployed, working, and secure.

---

### Quick Troubleshooting

*   **`gunicorn: command not found`**: You forgot to create or push `requirements.txt`.
*   **`TemplateNotFound: base.html`**: Your `templates` folder is named incorrectly (it must be all lowercase) or was not pushed to GitHub.
*   **`relation "user" does not exist`**: You have not successfully visited the one-time setup URL yet.
*   **`NameError: name 'app' is not defined`**: You placed the setup function *outside* the `create_app()` function in `app.py`. It must be inside.
