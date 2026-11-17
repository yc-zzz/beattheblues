import React, {useEffect, useState} from 'react';
import {API_URL, RECO_API_URL} from '../config';
import './profile.css'
import SongLinks from '../components/SongLinks';

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
    fetch(`${RECO_API_URL}/personality`,{
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
    const res = await fetch(`${RECO_API_URL}/personality`,{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'description', answers:answers, username: username})
    });
    const data = await res.json();
    set_description(data.description);
    set_submitted(true); //helps to keep track and dissappear the forms when user submits
  };

  const handle_get_playlist = async () => {//gets playlist, surprise
    const res = await fetch(`${RECO_API_URL}/personality`,{
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action: 'playlist', username: username})
    });
    const data = await res.json();
    set_playlist(data.playlist);
  };

  const playlist_add = async (song: {name: string; artist: string}) => {
    try {
      const response = await fetch(`${API_URL}/playlist`, {
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
    <main className='page profile-page'>
      <a href="/" className="back-link">← Back to home</a>
      <div className='page-heading'>
        <h1 className='page-title'>Find out your personality</h1>
        <p className='page-subtitle'>Answer a few questions and get a playlist that fits you.</p>
      </div>

      {submitted === false &&  questions.length > 0 && (//not submitted -> show the forms
        <form className='personality-form' onSubmit={(e) => {
          e.preventDefault();
          handle_submit();
        }}>
          {questions.map((q:any, index:number) => (//goes through the questions in the list
            <div className='field' key = {q.id}>
              <label htmlFor={`question-${index}`}>{q.question}</label>
              <textarea
              id={`question-${index}`}
              rows={2}
              value = {answers[index]}
              onChange={(e) => handle_input_change(index, e.target.value)}
              />
            </div>
          ))}
          <button className='btn btn-primary' type="submit">What's my personality?</button>
        </form>
      )}

      {submitted === true && (
        <section className='card results-block'>
          <h2 className='section-title'>Your personality</h2>
          <p className='personality-description'>{description}</p>
          <button type='button' className='btn btn-primary' onClick={handle_get_playlist}>Get my playlist</button>
        </section>
      )}
      
      {playlist.length >0 && (
      <section className='playlist-block'>
        <h2 className='section-title'>Recommended songs</h2>
          <ul className='song-list'>
            {playlist.map((song, idx) => {
              const name = song?.name || ''; // Asign to empty string first if song is not ready to prevent crashing
              const artist = song?.artist || '';
              return (
              <li key={idx} className="card song-card">
                <span className='song-name'>{name} <span className='song-artist'>by {artist}</span></span>
                <SongLinks song={`${name} by ${artist}`} />
                <button type='button' className="btn btn-outline" onClick={() => playlist_add(song)}>
                  + Add to playlist
                </button>
              </li>
              );
            })}
          </ul>
      </section>
      )}
    </main>
  );
}