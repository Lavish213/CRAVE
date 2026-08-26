import React from 'react';
import { TouchableOpacity } from 'react-native';

export const animateToRegionMock = jest.fn();
export const fitToCoordinatesMock = jest.fn();
export const mapViewProps: { current: any } = { current: null };

const MapView = React.forwardRef((props: any, ref: any) => {
  mapViewProps.current = props;
  React.useImperativeHandle(ref, () => ({
    animateToRegion: animateToRegionMock,
    fitToCoordinates: fitToCoordinatesMock,
  }));
  return React.createElement(React.Fragment, null, props.children);
});

export default MapView;
// Renders a real pressable (rather than null) so a test can simulate a
// marker tap via its testID -- map.tsx passes one per feature/cluster.
// Existing tests that don't care about marker presses are unaffected;
// they never queried for these elements before. Always supplies a
// stopPropagation stub -- map.tsx's real onPress handlers call
// event.stopPropagation() (a real fix: without it, a marker tap also
// bubbles to MapView's own onPress and immediately un-selects itself),
// and RTL's fireEvent.press() doesn't provide one on its own.
export const Marker = ({ onPress, testID, children }: any) =>
  React.createElement(TouchableOpacity, {
    onPress: (e: any) => onPress?.({ stopPropagation: () => {}, ...e }),
    testID,
  }, children);
export type Region = {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
};
