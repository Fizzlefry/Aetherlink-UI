import React from 'react';
import { SafeAreaView, Text, View, ScrollView } from 'react-native';
import Dashboard from './src/Dashboard';
import GenesisMemory from './src/GenesisMemory';
import AetherForge from './src/AetherForge';

export default function App() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0e0e0e' }}>
      <ScrollView>
        <View style={{ padding: 16 }}>
          <Text style={{ fontSize: 24, color: '#ffffff', marginBottom: 16 }}>
            Aetherlink Mobile Alpha
          </Text>
          <Dashboard />
          <GenesisMemory />
          <AetherForge />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}