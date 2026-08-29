import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

type PreferencesState = {
  compactMode: boolean;
  sidebarCollapsed: boolean;
};

const initialState: PreferencesState = {
  compactMode: true,
  sidebarCollapsed: false,
};

export const preferencesSlice = createSlice({
  name: "preferences",
  initialState,
  reducers: {
    setCompactMode: (state, action: PayloadAction<boolean>) => {
      state.compactMode = action.payload;
    },
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed;
    },
  },
});

export const { setCompactMode, toggleSidebar } = preferencesSlice.actions;
