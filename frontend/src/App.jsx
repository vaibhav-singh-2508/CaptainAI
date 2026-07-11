import Uploader from './components/Uploader'

function App() {
  const handleUploadSuccess = (result) => {
    // Sub-task 3 will navigate to the processing/editor view using result.job_id.
    // For now, the success state is shown inside Uploader itself.
    console.log('Upload succeeded:', result)
  }

  return <Uploader onUploadSuccess={handleUploadSuccess} />
}

export default App
