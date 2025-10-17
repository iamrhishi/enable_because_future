import React, { useState, useEffect, useRef } from 'react';

import '../styles/LandingPage.css';
import Header from './Header';

const backgroundImages = [
  'ellen-qin-bOOQ3z2WjOs-unsplash.jpg',
  'pexels-kseniachernaya-3965534.jpg',
  'pexels-kseniachernaya-3965545.jpg'
];

const backgroundPath = '/images/background/';
const logoPath = '/images/bcf_green_logo.png';
const cameraIcon = 'https://cdn-icons-png.flaticon.com/512/685/685655.png';
const hangerIcon = '/images/icons/clothes-hanger.png'; // Floating button icon
const wardrobePath = '/images/wardrobe/';

function LandingPage() {
  const [bgIndex, setBgIndex] = useState(0);
  const [outputImage, setOutputImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [tryonImage, setTryonImage] = useState(null);
  const [showWardrobe, setShowWardrobe] = useState(false);
  const [wardrobeImages, setWardrobeImages] = useState([]);
  const [wardrobeIndex, setWardrobeIndex] = useState(0);

  const fileInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const personImageBlobRef = useRef(null); // To store the blob from remove-bg

  function handleGalleryUpload() {
    if (galleryInputRef.current) {
      galleryInputRef.current.click();
    }
  }

  const handleWardrobeOpen = () => {
    setShowWardrobe(true);
    fetch('/api/wardrobe-images')
      .then(res => res.json())
      .then(data => {
        if (data.images) setWardrobeImages(data.images);
      });
  };

  const handleWardrobeClose = () => setShowWardrobe(false);

  const handleWardrobePrev = () => {
    setWardrobeIndex((prev) => (prev - 1 + wardrobeImages.length) % wardrobeImages.length);
  };

  const handleWardrobeNext = () => {
    setWardrobeIndex((prev) => (prev + 1) % wardrobeImages.length);
  };

  const handlePrev = () => {
    setBgIndex((prev) => (prev - 1 + backgroundImages.length) % backgroundImages.length);
  };

  const handleNext = () => {
    setBgIndex((prev) => (prev + 1) % backgroundImages.length);
  };

  const handleCameraClick = () => {
    fileInputRef.current.click();
  };

  // Handles camera upload (person image)
  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      setLoading(true);
      setError('');
      setOutputImage(null);
      setTryonImage(null);
      const formData = new FormData();
      formData.append('file', e.target.files[0]);
      try {
        const response = await fetch('/api/remove-bg', {
          method: 'POST',
          body: formData,
        });
        if (!response.ok) throw new Error('API error');
        const blob = await response.blob();
        setOutputImage(URL.createObjectURL(blob));
        personImageBlobRef.current = blob;
      } catch (err) {
        setError('Failed to process image.');
      } finally {
        setLoading(false);
      }
    }
  };

  // Handles gallery upload (cloth image), removes background, then calls tryon API
  const handleGalleryFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      if (!personImageBlobRef.current) {
        setError('Please upload a person image first.');
        return;
      }
      setLoading(true);
      setError('');
      setTryonImage(null);

      const clothFile = e.target.files[0];

      try {
        // Step 1: Check if the file already exists in wardrobe
        const wardrobeRes = await fetch('/api/wardrobe-images');
        const wardrobeData = await wardrobeRes.json();
        const wardrobeFiles = wardrobeData.images || [];
        const fileName = clothFile.name;

        if (!wardrobeFiles.includes(fileName)) {
          // Step 2: Save clothing image to wardrobe if not duplicate
          const saveClothingForm = new FormData();
          saveClothingForm.append('file', clothFile);
          await fetch('/api/save-clothing', {
            method: 'POST',
            body: saveClothingForm,
          });
        }

        // Step 3: Remove background from clothing image
        const removeBgForm = new FormData();
        removeBgForm.append('file', clothFile);
        const removeBgResp = await fetch('/api/remove-bg', {
          method: 'POST',
          body: removeBgForm,
        });
        if (!removeBgResp.ok) {
          setError('Failed to remove background from clothing image.');
          setLoading(false);
          return;
        }
        const clothBlob = await removeBgResp.blob();

        // Step 4: Call try-on API with person image and background-removed clothing image
        const formData = new FormData();
        formData.append('person_image', personImageBlobRef.current, 'person.png');
        formData.append('cloth_image', clothBlob, 'cloth.png');
        formData.append('cloth_type', searchValue || 'upper');
        formData.append('num_inference_steps', 90);

        const response = await fetch('/api/tryon', {
          method: 'POST',
          body: formData,
        });

        const contentType = response.headers.get('Content-Type') || '';
        if (response.ok && contentType.startsWith('image/')) {
          const tryonBlob = await response.blob();

          // Step 5: Remove background from try-on result
          const removeBgForm2 = new FormData();
          removeBgForm2.append('file', tryonBlob, 'tryon.png');
          const removeBgResp2 = await fetch('/api/remove-bg', {
            method: 'POST',
            body: removeBgForm2,
          });
          if (removeBgResp2.ok) {
            const finalBlob = await removeBgResp2.blob();
            setTryonImage(URL.createObjectURL(finalBlob));
          } else {
            setTryonImage(URL.createObjectURL(tryonBlob)); // fallback to original tryon image
            setError('Failed to remove background from try-on result.');
          }
        } else {
          const errorText = await response.text();
          setError('Failed to generate try-on result: ' + errorText);
        }
      } catch (err) {
        setError('Failed to generate try-on result.');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleRefresh = () => {
    setOutputImage(null);
    setTryonImage(null);
    setError('');
    setLoading(false);
    personImageBlobRef.current = null;
  };

  // Handle wardrobe image selection (simulate file input)
  const handleWardrobeSelect = async () => {
    if (!personImageBlobRef.current) {
      setError('Please upload a person image first.');
      return;
    }
    setLoading(true);
    setError('');
    setTryonImage(null);
    try {
      // Step 1: Remove background from wardrobe image
      const wardrobeImgUrl = wardrobePath + wardrobeImages[wardrobeIndex];
      const wardrobeImgResp = await fetch(wardrobeImgUrl);
      const wardrobeImgBlob = await wardrobeImgResp.blob();

      const removeBgForm = new FormData();
      removeBgForm.append('file', wardrobeImgBlob, wardrobeImages[wardrobeIndex]);
      const removeBgResp = await fetch('/api/remove-bg', {
        method: 'POST',
        body: removeBgForm,
      });
      if (!removeBgResp.ok) {
        setError('Failed to remove background from wardrobe image.');
        setLoading(false);
        return;
      }
      const clothBlob = await removeBgResp.blob();

      // Step 2: Call tryon API
      const formData = new FormData();
      formData.append('person_image', personImageBlobRef.current, 'person.png');
      formData.append('cloth_image', clothBlob, 'cloth.png');
      formData.append('cloth_type', searchValue || 'upper');
      formData.append('num_inference_steps', 11);
      const response = await fetch('/api/tryon', {
        method: 'POST',
        body: formData,
      });
      const contentType = response.headers.get('Content-Type') || '';
      if (response.ok && contentType.startsWith('image/')) {
        const tryonBlob = await response.blob();
        // Step 3: Remove background from tryon result
        const removeBgForm2 = new FormData();
        removeBgForm2.append('file', tryonBlob, 'tryon.png');
        const removeBgResp2 = await fetch('/api/remove-bg', {
          method: 'POST',
          body: removeBgForm2,
        });
        if (removeBgResp2.ok) {
          const finalBlob = await removeBgResp2.blob();
          setTryonImage(URL.createObjectURL(finalBlob));
        } else {
          setTryonImage(URL.createObjectURL(tryonBlob));
          setError('Failed to remove background from try-on result.');
        }
      } else {
        const errorText = await response.text();
        setError('Failed to generate try-on result: ' + errorText);
      }
    } catch (err) {
      setError('Failed to generate try-on result.');
    } finally {
      setLoading(false);
      setShowWardrobe(false);
    }
  };

  return (
    <div className="landing-page"
      style={{
        backgroundImage: `url(${backgroundPath + backgroundImages[bgIndex]})`,
        transition: 'background-image 0.5s ease-in-out',
      }}
    >
      <Header />
      <div className="center-content" style={{ position: 'relative' }}>
        <div className="bg-carousel">
          {backgroundImages.map((img, idx) => (
            <img
              key={img}
              src={backgroundPath + img}
              alt={`bg-thumb-${idx}`}
              className={`bg-thumb${bgIndex === idx ? ' selected' : ''}`}
              onClick={() => setBgIndex(idx)}
            />
          ))}
        </div>
        {!outputImage && !tryonImage && (
          <>
            <button className="camera-btn" onClick={handleCameraClick}>
              <img src={cameraIcon} alt="Camera" className="camera-icon" />
            </button>
            <input
              type="file"
              accept="image/*"
              ref={fileInputRef}
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            {loading && <div className="output-status">Processing...</div>}
            {error && <div className="output-error">{error}</div>}
          </>
        )}
        {tryonImage ? (
          <div>
            <img src={tryonImage} alt="Try-On Result" className="output-image-human"/>
          </div>
        ) : (
          outputImage && (
            <div>
              <img src={outputImage} alt="Output" className="output-image-human"/>
              <button className="refresh-btn" onClick={handleRefresh} title="Upload another image">&#x21bb;</button>
            </div>
          )
        )}
      </div>
      <div className="garment-search-bar-wrapper">
        <div className="garment-search-bar-group overlay-group">
          <input
            className="garment-search-bar"
            type="text"
            placeholder="Search for garments or paste a URL…"
            value={searchValue}
            onChange={e => setSearchValue(e.target.value)}
          />
          <button className="search-upload-btn circle-btn overlay-btn" title="Upload from gallery" onClick={handleGalleryUpload}>
            <img src={cameraIcon} alt="Upload" />
            <input
              type="file"
              accept="image/*"
              className="search-upload-input"
              onChange={handleGalleryFileChange}
              ref={galleryInputRef}
            />
          </button>
        </div>
        <button className="refresh-btn search-refresh-btn" onClick={handleRefresh} title="Try another">&#x21bb;</button>
      </div>
      {/* Floating wardrobe button */}
      <button
        className="floating-wardrobe-btn"
        onClick={handleWardrobeOpen}
        title="Open Wardrobe"
      >
        <img src={hangerIcon} alt="Wardrobe" />
      </button>
      {/* Wardrobe modal/carousel */}
      {showWardrobe && (
        <div className="wardrobe-modal">
          <div className="wardrobe-modal-content">
            <button className="wardrobe-close-btn" onClick={handleWardrobeClose}>&times;</button>
            <div className="wardrobe-carousel">
              <button className="wardrobe-nav-btn" onClick={handleWardrobePrev}>&uarr;</button>
              <div className="wardrobe-carousel-images">
                {wardrobeImages.length > 0 &&
                  [wardrobeIndex - 1, wardrobeIndex, wardrobeIndex + 1].map((idx, i) => {
                    // Wrap around for circular carousel
                    const realIdx = (idx + wardrobeImages.length) % wardrobeImages.length;
                    return (
                      <img
                        key={realIdx}
                        src={wardrobePath + wardrobeImages[realIdx]}
                        alt={`wardrobe-${realIdx}`}
                        className={
                          'wardrobe-image' +
                          (i === 1 ? ' wardrobe-image-active' : ' wardrobe-image-inactive')
                        }
                      />
                    );
                  })}
              </div>
              <button className="wardrobe-nav-btn" onClick={handleWardrobeNext}>&darr;</button>
            </div>
            {/* <button className="wardrobe-select-btn" onClick={handleWardrobeSelect}>
              Try This
            </button> */}
          </div>
        </div>
      )}
      {outputImage && !tryonImage && (
        <div className="checkbox-upper-lower">
          <label className="checkbox-upper">
            <input
              type="checkbox"
              checked={searchValue === 'upper'}
              onChange={() => setSearchValue('upper')}
            />
            <span>Top Garment</span>
          </label>
          <label className="checkbox-lower">
            <input
              type="checkbox"
              checked={searchValue === 'lower'}
              onChange={() => setSearchValue('lower')}
            />
            <span>Bottom Garment</span>
          </label>
        </div>
      )}
    </div>
  );
}

export default LandingPage;
