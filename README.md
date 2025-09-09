# Uploading Data from DOCX Tables to the DB via Django Admin

For my project I implemented the ability to upload tables from DOCX files directly into the database through the Django admin panel.

- [utils.py](./documents/utils/utils.py) - contains the core logic for processing DOCX files
- The **DocxToDB** class converts tables into CSV which is then imported into PostgreSQL
- The **ImportDocument402n** subclass extends the logic when needed (e.g., field mapping) 

---

### How it looks in the admin panel
![Admin Upload Example](assets/admin.jpg)

### Example of using uploaded data in my project
![Project Data Example](assets/example.gif)
