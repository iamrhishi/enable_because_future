import React from 'react';
import '../styles/Header.css';




function Header({ onUserClick, onBodyMeasureClick }) {
  return (
    <header className="main-header">
      <div className="header-left">
         <img src="/images/bcf_green_logo.png" alt="Logo" className="header-logo" />
      </div>
      <div className="header-right">
        <button className="header-btn body-btn" onClick={onBodyMeasureClick} title="Body Measurement">
           <img src="/images/icons/body-measure.png" alt="Body Measurement" />
        </button>
        <button className="header-btn user-btn" onClick={onUserClick} title="User">
           <img src="/images/icons/people.png" alt="User" />
        </button>
      </div>
    </header>
  );
}


export default Header;
