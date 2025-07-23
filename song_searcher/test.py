from song_search import Search

song_search = Search()

def too_many_requests():
    query = input("Search for a song: ")
    print(song_search.return_song(query))
    print(song_search.return_song(query))
    print(song_search.return_song(query))
    print(song_search.return_song(query))
    print(song_search.return_song(query))
    print(song_search.return_song(query))

def null_input(): 
    query = None
    print(song_search.return_song(query))
