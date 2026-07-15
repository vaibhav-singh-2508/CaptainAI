/**
 * useSubtitleEditor — manages segment text edits and the current style preset.
 *
 * Initialised from the ProcessedResult that arrives via the SSE "ready" event.
 *
 * Returned interface:
 *   segments          — current array of Segment objects (with editable corrected_text)
 *   style             — current StylePreset object
 *   updateSegmentText(id, newText) — update a single segment's corrected_text
 *   setStyle(preset)              — replace the whole style object
 *   initFromResult(result)        — seed state from the SSE ready payload
 */

import { useReducer, useCallback } from 'react'

// ── Style preset definitions (mirrors backend style_engine.py) ─────────────

export const STYLE_PRESETS = {
  cinematic: {
    preset_name: 'cinematic',
    font_name: 'Arial',
    font_size: 28,
    primary_color: '#FFFFFF',
    outline_color: '#000000',
    position: 'bottom',
    background_box: false,
    bold: true,
  },
  social: {
    preset_name: 'social',
    font_name: 'Arial',
    font_size: 32,
    primary_color: '#FFFF00',
    outline_color: '#000000',
    position: 'bottom',
    background_box: true,
    bold: true,
  },
  education: {
    preset_name: 'education',
    font_name: 'Arial',
    font_size: 24,
    primary_color: '#FFFFFF',
    outline_color: '#0000FF',
    position: 'bottom',
    background_box: true,
    bold: false,
  },
  minimal: {
    preset_name: 'minimal',
    font_name: 'Arial',
    font_size: 22,
    primary_color: '#FFFFFF',
    outline_color: '#000000',
    position: 'bottom',
    background_box: false,
    bold: false,
  },
  karaoke: {
    preset_name: 'karaoke',
    font_name: 'Arial',
    font_size: 30,
    primary_color: '#00FFFF',
    outline_color: '#000000',
    position: 'bottom',
    background_box: false,
    bold: true,
  },
}

// ── Reducer ────────────────────────────────────────────────────────────────

const initialState = {
  segments: [],
  style: STYLE_PRESETS.minimal,
}

function reducer(state, action) {
  switch (action.type) {
    case 'INIT': {
      return {
        segments: action.segments,
        style: action.style,
      }
    }
    case 'UPDATE_SEGMENT_TEXT': {
      return {
        ...state,
        segments: state.segments.map((seg) =>
          seg.id === action.id
            ? { ...seg, text: action.text }
            : seg
        ),
      }
    }
    case 'SET_STYLE': {
      return { ...state, style: action.style }
    }
    case 'RESET': {
      return initialState
    }
    default:
      return state
  }
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useSubtitleEditor() {
  const [state, dispatch] = useReducer(reducer, initialState)

  /**
   * Seed state from the SSE ready payload.
   * result.subtitles  — array of Segment objects
   * result.granite_result — GraniteResult with style_preset name
   */
  const initFromResult = useCallback((result) => {
    const { subtitles, granite_result } = result
    const presetName = granite_result?.style_preset ?? 'minimal'
    const style = STYLE_PRESETS[presetName] ?? STYLE_PRESETS.minimal

    dispatch({
      type: 'INIT',
      segments: subtitles ?? [],
      style,
    })
  }, [])

  const updateSegmentText = useCallback((id, text) => {
    dispatch({ type: 'UPDATE_SEGMENT_TEXT', id, text })
  }, [])

  const setStyle = useCallback((style) => {
    dispatch({ type: 'SET_STYLE', style })
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' })
  }, [])

  return {
    segments: state.segments,
    style: state.style,
    updateSegmentText,
    setStyle,
    initFromResult,
    reset,
  }
}
