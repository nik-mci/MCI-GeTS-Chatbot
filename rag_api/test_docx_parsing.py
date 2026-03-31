from docx import Document
import os

def test_docx(filename):
    path = os.path.join("..", "GeTS Itineraries", filename)
    print(f"Testing: {path}")
    if not os.path.exists(path):
        print("File not found!")
        return
    
    try:
        doc = Document(path)
        text = []
        for p in doc.paragraphs:
            if p.text.strip():
                text.append(p.text.strip())
        
        print(f"Read {len(text)} paragraphs.")
        full_text = "\n".join(text)
        print(f"Total characters: {len(full_text)}")
        print(f"First 200 chars: {full_text[:200]}")
        print(f"Contains 'North East': {'north east' in full_text.lower()}")
        print(f"Contains 'Northeast': {'northeast' in full_text.lower()}")
    except Exception as e:
        print(f"Error reading docx: {e}")

if __name__ == "__main__":
    test_docx("WONDERS OF NORTH-EAST WITH WILDLIFE IN KAZIRANGA.docx")
    print("-" * 20)
    test_docx("DELIGHTFUL NORTH-EAST_ Rewritten Itinerary.docx")
