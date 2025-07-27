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

  useEffect(() => {
    fetch('https://beattheblues-reco.onrender.com/personality',{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'display'})
    })
    .then(res => res.json())
    .then(data => {
      set_questions(data);//stored questions
      set_answers(Array(data.length).fill(''));//blank answers stored
    });
  },[]);

  const handle_input_change = (index: number, value: string) => {//handles updates to answer
    const updated_answers = [...answers];
    updated_answers[index] = value;
    set_answers(updated_answers);
  };

  const handle_submit = async () => { //handles submission of personality answer to backend
    const res = await fetch('https://beattheblues-reco.onrender.com/personality',{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'description', answers:answers})
    });
    const data = await res.json();
    set_description(data.description);
    set_submitted(true); //helps to keep track and dissappear the forms when user submits
  };

  const handle_get_playlist = async () => {//gets playlist, surprise
    const res = await fetch('https://beattheblues-reco.onrender.com/personality',{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'playlist'})
    });
    const data = await res.json();
    set_playlist(data.playlist);
  };


  return (
    <div className='profile-page'>
      <h3>
        Find out your personality!
      </h3>
      <a href="/" className="home-link">Return to Home</a>
      {submitted === false &&  questions.length > 0 && (
        <form className='personality-form'>
          {questions.map((q:any, index:number) => (
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
              const query = encodeURI(`${name} by ${artist}`);
              return (
              <li key={idx} className="song-row">
                <span>{song.name} by {song.artist}</span>
                <div className="search-buttons">
                  <a href={`https://www.youtube.com/results?search_query=${query}`} target="_blank" rel="noopener noreferrer">
                  <img src={youtubelogo} alt="YouTube" className="search-icon" />
                  </a>
                  <a href={`https://open.spotify.com/search/${query}`} target="_blank" rel="noopener noreferrer">
                  <img src={spotifylogo} alt="Spotify" className="search-icon" />
                  </a>
                  <a href={`https://www.google.com/search?q=${query}`} target="_blank" rel="noopener noreferrer">
                  <img src={googlelogo} alt="Google" className="search-icon" />
                  </a>
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