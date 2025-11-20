# keyphrases.py
# -*- coding: utf-8 -*-
"""Definition der Keyphrase-Sets für die Segmenterkennung."""

# Dictionary:
#   Schlüssel = Spaltenname im Panel (z.B. "key_phrase_1")
#   Wert      = Liste von Key Phrases (Substrings, die in "text" gesucht werden)
KEYPHRASE_SETS: dict[str, list[str]] = {
    "key_phrase_1": [
        # Beginn Prepared Remarks
        "turn the floor over to",
        "turn the call over to",
        "hand the conference call over to",
        "thank you for standing by",
        "thank you for joining",
        "Thank you and welcome everyone",
        "turn the call over to",
        "happy to talk to you today",
        "hand over to",
        "hand it over to",
        "You may begin",
        "good morning everyone",
        "Good afternoon, everyone",
        "Welcome, everyone",
        "Welcome everyone",
        "opening remarkss",
        "Welcome to",
        "hand it over to",
    ],
    "key_phrase_2": [
        # ==============================
        # Beginn Q&A
        # ==============================
        "first question comes from",  # die beste Key Phrase!
        "The floor is now open for questions",
        "we will limit participants to one question",
        "we will now start the Q&A session",
        "we are going to take the Q&A now",
        "ready to answer all your questions",
        "starting with the Q&A",
        "we can start with the Q&A",
        "start with the Q&A",
        "we have the Q&A",
        "happy to take your question",
        "ready to take your question",
        "here to answer your questions",
        "now to Q&A",
        "ready to go to the Q&A",
        "We are now ready for Q&A",
        "open up the Q&A",
        "manage the Q&A",
        "hand it back to the operator for the Q&A",
        "conducting a question and answer session",
        "Our first question today",
        "we are going to take the Q&A now",
        "think the first question is from",
        "ready for questions",
        "ready for the first question",
        "available to answer your questions",
        "We will now begin the question and answer session",
        "first question is from",
        # "take your question", # zu häufig und maximal unpräzise
        # "now we can start with the Q&A part", # kommt gar nicht vor
        # "now we can start with the Q&A", # kommt gar nicht vor
        # "happy to take your questions", # kommt gar nicht vor
        # "ready to take your questions", # kommt gar nicht vor
        # "take your questiones", # kommt gar nicht vor
        # "the first question", # extrem häufig und extrem unpräzise
        # "answer your question", # zu häufig und zu unpräzise
        # "answer your questions", # kommt gar nicht vor
    ],
    # Beispiel für Erweiterung:
    # "key_phrase_3": [
    #     "forward-looking statements",
    # ],
}
