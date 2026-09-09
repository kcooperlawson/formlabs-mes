Put an update package in this folder.

It will be one zip file, named after the version it brings, for example
mes_update_PT-V3.41.zip. Copy it in here, then run START_HERE.bat in the
folder above this one and choose 7.

Nothing in this folder runs on its own. The zip holds the changed files and a
list of them with checksums; the program that reads it lives in setup\ on this
PC and was installed with the rest of the application.

Before it changes anything it takes a database backup and copies the whole
project into rollback\. After it writes the files it starts the application to
prove it works, and if that fails it puts the old version back on its own.

Packages that have been applied are moved into applied\ so the same one is not
run twice by accident.
