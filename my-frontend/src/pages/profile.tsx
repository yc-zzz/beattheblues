import React, {useEffect, useState} from 'react';
import './profile.css'
import youtubelogo from '../pics/youtube_logo.png';
import spotifylogo from '../pics/spotify.png';
import googlelogo from '../pics/google.png';

export default function Personality() {
  const [questions, set_questions] = useState([]); //questions obtained from backend
  const [answers, set_answers] = useState<string[]>([]); //answers by users
  const [description, set_description] = useState(''); //personality description
  const [playlist, set_playlist] = useState<{name: string,artist: string}[]>([]);
  const [submitted, set_submitted] = useState(false); //state tracker for submission
  const [username, set_username] = useState('');
  
  useEffect(() => {
    const stored_user = localStorage.getItem('username');
    if (stored_user) set_username(stored_user);
  }, []);

  useEffect(() => {
    fetch('https://beattheblues-reco.onrender.com/personality',{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'display'})
    })
    .then(res => res.json())
    .then(data => {
      set_questions(data);//stored questions
      const saved_answer = localStorage.getItem('personality_answers');
      if(saved_answer){
        const parsed_answers = JSON.parse(saved_answer);
        set_answers(parsed_answers);
      }else{
        set_answers(Array(data.length).fill(''));//blank answers stored
      }
    });
  },[]);

  const handle_input_change = (index: number, value: string) => {//handles updates to answer
    const updated_answers = [...answers];
    updated_answers[index] = value;
    set_answers(updated_answers);
    localStorage.setItem('personality_answers', JSON.stringify(updated_answers)); //cache the answers locally to save them
  };

  const handle_submit = async () => { //handles submission of personality answer to backend
    const res = await fetch('https://beattheblues-reco.onrender.com/personality',{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'description', answers:answers, username: username})
    });
    const data = await res.json();
    set_description(data.description);
    set_submitted(true); //helps to keep track and dissappear the forms when user submits
  };

  const handle_get_playlist = async () => {//gets playlist, surprise
    const res = await fetch('https://beattheblues-reco.onrender.com/personality',{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'playlist', username: username})
    });
    const data = await res.json();
    set_playlist(data.playlist);
  };

  const playlist_add = async (song: {name: string; artist: string}) => {
    try {
      const response = await fetch('https://beattheblues.onrender.com/playlist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, song: `${song.name} by ${song.artist}`})
      });
      const data = await response.json();
      alert(data.message);
    } 
    catch (err){
      alert('Failed to save song');
      console.error(err);
    }
  };

  return (
    <div className='profile-page'>
      <h3>
        Find out your personality!
      </h3>
      <a href="/" className="home-link">Return to Home</a>
      {submitted === false &&  questions.length > 0 && (//not submitted -> show the forms
        <form className='personality-form'>
          {questions.map((q:any, index:number) => (//goes through the questions in the list
            <div className='question-block' key = {q.id}>
              <label>{q.question}</label>
              <textarea
              value = {answers[index]}
              onChange={(e) => handle_input_change(index, e.target.value)}
              />
            </div>
          ))}
          <button type="button" onClick={handle_submit}>What's my personality?</button>
        </form>
      )}

      {submitted === true && (
        <div className='results-block'>
          <h2>Your personality:</h2>
          <p>{description}</p>
          <button onClick={handle_get_playlist}> Get playlist</button>
        </div>
      )}
      
      {playlist.length >0 && (
      <div className='playlist-block'>
        <h2>recommended songs</h2>
          <ul className='song-list'>
            {playlist.map((song, idx) => {
              const name = song?.name || ''; // Asign to empty string first if song is not ready to prevent crashing
              const artist = song?.artist || '';
              const full_name = encodeURI(`${name} by ${artist}`);
              return (
              <li key={idx} className="song-row">
                <span>{song.name} by {song.artist}</span>
                <div className="search-buttons">
                  <a href={`https://www.youtube.com/results?search_query=${full_name}`} target="_blank" rel="noopener noreferrer">
                  <img src={youtubelogo} alt="YouTube" className="search-icon" />
                  </a>
                  <a href={`https://open.spotify.com/search/${encodeURI(`${name} ${artist}`)}`} target="_blank" rel="noopener noreferrer">
                  <img src={spotifylogo} alt="Spotify" className="search-icon" />
                  </a>
                  <a href={`https://www.google.com/search?q=${full_name}`} target="_blank" rel="noopener noreferrer">
                  <img src={googlelogo} alt="Google" className="search-icon" />
                  </a>
                  <button className="add-button" onClick={() => playlist_add(song)}>
                    Add to Playlist
                  </button>
                </div>
              </li>
              );
            })}
          </ul>
      </div>
      )}
    </div>
  );
}